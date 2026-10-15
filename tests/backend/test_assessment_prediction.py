"""Assessment HTTP contracts using service doubles and migrated in-memory SQLite.

No server is started. Real V17 loading/prediction and artifact reads are forbidden.
TEST_ONLY_LABEL values below are rendering/transport fixtures, not clinical advice.
"""

from copy import deepcopy
import os
import secrets
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from alembic import command
from sqlalchemy.exc import OperationalError

from backend.app import create_app
from backend.app.api.patients import assessment_data
from backend.app.auth.security import hash_password, issue_token
from backend.app.database import db
from backend.app.models import ClinicalAssessment, Patient, User
from backend.app.services.v17 import V17Service, V17Error, V17Unavailable, V17InvalidInput
from test_database import migration_config
from test_patients import valid_payload


EXPECTED_OUTPUTS = (
    "Herbal Therapy Strategy", "Lifestyle Recommendations",
    "Therapeutic Yoga Module", "Follow-up Recommendation",
)
CONTROLLED_PREDICTION = {
    "model_version": "AyurSage_v17", "status": "pending_clinical_review", "persisted": False,
    "outputs": {name: f"TEST_ONLY_LABEL_{index}" for index, name in enumerate(EXPECTED_OUTPUTS)},
}


class AssessmentPredictionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("isolated-contract-test-password")

    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        for guard in (
            patch.object(V17Service, "load", side_effect=AssertionError("Real model loading forbidden")),
            patch.object(V17Service, "predict", side_effect=AssertionError("Real service prediction forbidden")),
            patch("backend.app.services.v17.verify_workspace_buffers", side_effect=AssertionError("Artifact reads forbidden")),
        ):
            guard.start()
            self.addCleanup(guard.stop)
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": secrets.token_urlsafe(48), "V17_MODEL_LOADING_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        with db.engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")
        self.users = {}
        for name, role_id in (("owner", 1), ("other", 1), ("doctor", 2), ("admin", 3), ("receptionist", 4)):
            user = User(email=f"{name}@example.invalid", role_id=role_id, password_hash=self.password_hash)
            db.session.add(user)
            self.users[name] = user
        db.session.flush()
        patient = Patient(owner_user_id=self.users["owner"].id)
        db.session.add(patient)
        db.session.commit()
        self.owner_id, self.patient_id = self.users["owner"].id, patient.id
        self.headers = {name: {"Authorization": "Bearer " + issue_token(user)} for name, user in self.users.items()}
        self.url = f"/api/patients/{self.patient_id}/assessments"
        self.client = self.app.test_client()
        self.predict = Mock(return_value=deepcopy(CONTROLLED_PREDICTION))
        self.app.extensions["v17"] = SimpleNamespace(predict=self.predict)

    def submit(self, payload=None, headers=None, url=None):
        return self.client.post(url or self.url, json=payload if payload is not None else {**valid_payload(), "predict": True},
                                headers=self.headers["owner"] if headers is None else headers)

    def count(self):
        return db.session.query(ClinicalAssessment).count()

    def test_save_only_false_and_omitted_skip_service_and_preserve_schema(self):
        for payload in (valid_payload(), {**valid_payload(), "predict": False}):
            response = self.submit(payload)
            self.assertEqual(response.status_code, 201)
            data = response.get_json()
            self.assertEqual(set(data), {"assessment"})
            self.assertEqual(set(data["assessment"]), {"id", "patient_id", "recorded_by_user_id", "created_at", "inputs", "notes"})
            self.assertEqual(data["assessment"]["inputs"], payload["inputs"])
            self.assertEqual(data["assessment"]["recorded_by_user_id"], self.owner_id)
        self.predict.assert_not_called()
        self.assertEqual(self.count(), 2)

    def test_controlled_prediction_is_response_only_and_pending_review(self):
        payload = {**valid_payload(), "predict": True}
        response = self.submit(payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(set(data), {"assessment", "prediction"})
        self.assertEqual(data["prediction"], CONTROLLED_PREDICTION)
        self.assertEqual(set(data["prediction"]["outputs"]), set(EXPECTED_OUTPUTS))
        self.predict.assert_called_once_with(payload["inputs"])
        self.assertEqual(self.count(), 1)
        row = db.session.get(ClinicalAssessment, data["assessment"]["id"])
        self.assertEqual(row.inputs, payload["inputs"])
        self.assertEqual(row.notes, payload["notes"])
        self.assertEqual(row.review_state, "pending_review")
        self.assertEqual(row.review_history, [])
        detail = self.client.get(self.url + f"/{row.id}", headers=self.headers["owner"]).get_json()
        self.assertEqual(detail, {"assessment": data["assessment"]})
        history = self.client.get(self.url, headers=self.headers["owner"]).get_json()
        self.assertEqual(history["assessments"], [data["assessment"]])
        self.assertNotIn("TEST_ONLY_LABEL", str(detail) + str(history))

    def test_invalid_input_and_predict_controls_return_400_before_service_or_write(self):
        payloads = []
        for invalid in ("true", 1, None):
            payloads.append({**valid_payload(), "predict": invalid})
        missing = valid_payload()
        del missing["inputs"]["Disease"]
        payloads.append({**missing, "predict": True})
        for name, value in (("Pulse Rate", True), ("Pulse Rate", "1"), ("Disease", None), ("Pulse Rate", float("inf"))):
            invalid = valid_payload()
            invalid["inputs"][name] = value
            payloads.append({**invalid, "predict": True})
        extra = valid_payload()
        extra["inputs"]["Unexpected field"] = "test"
        payloads.append({**extra, "predict": True})
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.submit(payload)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("assessment", response.get_json())
                self.assertNotIn("prediction", response.get_json())
        self.predict.assert_not_called()
        self.assertEqual(self.count(), 0)

    def test_model_validation_unavailable_and_inference_failures_have_no_success_or_row(self):
        for error in (V17InvalidInput(), V17Unavailable(), V17Error()):
            with self.subTest(status=error.status):
                self.predict.reset_mock()
                self.predict.side_effect = error
                response = self.submit()
                self.assertEqual(response.status_code, error.status)
                self.assertEqual(response.get_json(), {"error": {
                    "code": error.status, "reason": error.reason, "message": error.message,
                }})
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.predict.assert_called_once()
                self.assertEqual(self.count(), 0)

    def test_authentication_roles_and_ownership_deny_before_prediction_for_both_modes(self):
        for predict in (False, True):
            cases = [({}, self.url, 401), ({"Authorization": "Bearer invalid-test-token"}, self.url, 401)]
            cases += [(self.headers[role], self.url, 403) for role in ("doctor", "admin", "receptionist")]
            cases += [(self.headers["other"], self.url, 404), (self.headers["owner"], "/api/patients/999999/assessments", 404)]
            for headers, url, status in cases:
                with self.subTest(predict=predict, status=status):
                    response = self.submit({**valid_payload(), "predict": predict}, headers, url)
                    self.assertEqual(response.status_code, status)
                    self.assertNotIn("assessment", response.get_json())
                    self.assertNotIn("prediction", response.get_json())
        self.predict.assert_not_called()
        self.assertEqual(self.count(), 0)

    def test_snapshot_precedes_commit_in_both_modes_without_post_commit_orm_reads(self):
        original_serializer = assessment_data
        original_commit = db.session.commit
        for predict in (False, True):
            events = []
            def snapshot(row):
                self.assertTrue(db.session().in_transaction())
                self.assertNotIn("commit", events)
                self.assertIsNotNone(row.id)
                self.assertIsNotNone(row.created_at)
                events.append("snapshot")
                return original_serializer(row)
            def commit():
                self.assertEqual(events, ["snapshot"])
                original_commit()
                events.append("commit")
            with patch("backend.app.api.patients.assessment_data", side_effect=snapshot), patch.object(db.session, "commit", side_effect=commit):
                response = self.submit({**valid_payload(), "predict": predict})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(events, ["snapshot", "commit"])
        self.assertEqual(self.count(), 2)

    def test_refresh_and_commit_failures_roll_back_without_returning_prediction(self):
        for operation in ("refresh", "commit"):
            for predict in (False, True):
                with self.subTest(operation=operation, predict=predict):
                    error = OperationalError("TEST_SQL", {}, Exception("PRIVATE_TEST_DETAIL"))
                    with patch.object(db.session, operation, side_effect=error):
                        response = self.submit({**valid_payload(), "predict": predict})
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.get_json(), {"error": {"code": 503, "message": "Service Unavailable"}})
                    self.assertNotIn("PRIVATE_TEST_DETAIL", response.get_data(as_text=True))
                    self.assertEqual(self.count(), 0)
        # The existing rollback handler leaves the session reusable.
        self.assertEqual(self.submit({**valid_payload(), "predict": False}).status_code, 201)
        self.assertEqual(self.count(), 1)
