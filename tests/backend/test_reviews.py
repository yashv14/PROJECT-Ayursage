"""Reserved review state/history; synthetic SQL fixtures are not authorized reviews."""

import io
import os
import secrets
import unittest
from unittest.mock import patch

from alembic import command
from sqlalchemy import delete, insert, inspect, select, update
from sqlalchemy.exc import IntegrityError

from backend.app import create_app
from backend.app.auth.security import hash_password, issue_token
from backend.app.database import db
from backend.app.models import AssessmentReview, ClinicalAssessment, Patient, User
from backend.app.models.review import REVIEW_STATES, validate_review_transition, ReviewWriteBlocked, ReviewHistoryImmutable
from test_database import migration_config
from test_patients import valid_payload


class ReviewFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("isolated-review-fixture-password")

    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "JWT_SECRET_KEY": secrets.token_urlsafe(48)})
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        with db.engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")
        self.users = {}
        for name, role in (("patient", 1), ("doctor", 2), ("admin", 3)):
            user = User(email=name + "@example.invalid", role_id=role, password_hash=self.password_hash)
            db.session.add(user)
            self.users[name] = user
        db.session.flush()
        patient = Patient(owner_user_id=self.users["patient"].id)
        db.session.add(patient)
        db.session.flush()
        self.assessment = ClinicalAssessment(patient_id=patient.id, recorded_by_user_id=self.users["patient"].id, inputs=valid_payload()["inputs"])
        db.session.add(self.assessment)
        db.session.commit()
        self.headers = {name: {"Authorization": "Bearer " + issue_token(user)} for name, user in self.users.items()}
        self.client = self.app.test_client()
        self.url = f"/api/patients/{patient.id}/assessments"

    def fixture(self, sequence=1, from_state="pending_review", to_state="returned_for_changes", **changes):
        values = {"assessment_id": self.assessment.id, "sequence": sequence,
                  "actor_user_id": self.users["doctor"].id, "from_state": from_state,
                  "to_state": to_state, "reason": "synthetic historical fixture"}
        values.update(changes)
        return values

    def seed_history(self, **values):
        # Deliberate test-only low-level connection write, outside ORM protection.
        with db.engine.begin() as connection:
            connection.execute(insert(AssessmentReview.__table__), self.fixture(**values))
        db.session.expire_all()

    def test_new_and_legacy_assessments_are_pending_without_prediction(self):
        self.assertEqual(self.assessment.review_state, "pending_review")
        self.assessment.inputs = None
        db.session.commit()
        self.assertEqual(self.assessment.review_state, "pending_review")
        self.assertEqual(self.assessment.review_history, [])
        with self.assertRaises(AttributeError):
            self.assessment.review_state = "approved"

    def test_reserved_transition_graph(self):
        allowed = {("pending_review", "approved"), ("pending_review", "returned_for_changes"), ("returned_for_changes", "pending_review")}
        for previous in REVIEW_STATES:
            for following in REVIEW_STATES:
                with self.subTest(previous=previous, following=following):
                    if (previous, following) in allowed:
                        validate_review_transition(previous, following)
                    else:
                        with self.assertRaises(ValueError):
                            validate_review_transition(previous, following)

    def test_invalid_decision_values(self):
        for previous, following in ((None, "approved"), ("pending_review", None), ([], "approved"), ("unknown", "approved"), ("pending_review", "doctor_approved")):
            with self.assertRaises(ValueError):
                validate_review_transition(previous, following)

    def test_inconsistent_history_cannot_project_an_approved_state(self):
        self.seed_history(sequence=2, from_state="pending_review", to_state="approved")
        with self.assertRaisesRegex(ValueError, "Invalid review history"):
            _ = self.assessment.review_state

    def test_state_chain_must_start_pending_and_follow_previous_event(self):
        self.seed_history(sequence=1, from_state="returned_for_changes", to_state="pending_review")
        with self.assertRaisesRegex(ValueError, "Invalid review history"):
            _ = self.assessment.review_state

    def test_ordered_history_actor_timestamps_and_previous_decisions_retained(self):
        self.seed_history(sequence=1)
        self.seed_history(sequence=2, from_state="returned_for_changes", to_state="pending_review", actor_user_id=self.users["patient"].id)
        self.seed_history(sequence=3, from_state="pending_review", to_state="approved")
        history = self.assessment.review_history
        self.assertEqual([row.to_state for row in history], ["returned_for_changes", "pending_review", "approved"])
        self.assertEqual(self.assessment.review_state, "approved")
        self.assertEqual(history[0].actor.id, self.users["doctor"].id)
        self.assertTrue(all(row.decided_at is not None for row in history))
        self.assertEqual([row.sequence for row in history], [1, 2, 3])
        self.assertEqual(db.session.query(AssessmentReview).count(), 3)

    def test_decision_writes_are_blocked_for_all_actors_and_states(self):
        for user in self.users.values():
            for decision in ("approved", "returned_for_changes"):
                db.session.add(AssessmentReview(**self.fixture(actor_user_id=user.id, to_state=decision)))
                with self.assertRaises(ReviewWriteBlocked):
                    db.session.commit()
                db.session.rollback()
        self.assertEqual(db.session.query(AssessmentReview).count(), 0)
        self.assertEqual(self.assessment.review_state, "pending_review")

    def test_patient_and_privileged_roles_cannot_use_review_http_actions(self):
        for actor in (None, "patient", "doctor", "admin"):
            headers = {} if actor is None else self.headers[actor]
            for suffix in ("/review", "/reviews", "/approve"):
                response = self.client.post(self.url + f"/{self.assessment.id}" + suffix, json={"decision": "approved"}, headers=headers)
                self.assertEqual(response.status_code, 404)  # No endpoint is registered.
        for actor in ("doctor", "admin"):
            self.assertEqual(self.client.get(self.url + f"/{self.assessment.id}", headers=self.headers[actor]).status_code, 403)
        self.assertEqual(db.session.query(AssessmentReview).count(), 0)

    def test_patient_cannot_inject_review_fields_on_assessment_creation(self):
        for key in ("review_state", "review_history", "decision", "actor_user_id", "decided_at"):
            payload = valid_payload()
            payload[key] = "approved"
            self.assertEqual(self.client.post(self.url, json=payload, headers=self.headers["patient"]).status_code, 400)
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 1)
        self.assertEqual(db.session.query(AssessmentReview).count(), 0)

    def test_history_attributes_cannot_be_overwritten(self):
        self.seed_history()
        row = self.assessment.review_history[0]
        for key, value in (("reason", "replacement"), ("to_state", "approved"), ("actor_user_id", self.users["patient"].id), ("sequence", 2)):
            setattr(row, key, value)
            with self.assertRaises(ReviewHistoryImmutable):
                db.session.commit()
            db.session.rollback()
        self.assertEqual(row.to_state, "returned_for_changes")
        self.assertEqual(row.reason, "synthetic historical fixture")

    def test_history_cannot_be_deleted_or_detached(self):
        self.seed_history()
        row = self.assessment.review_history[0]
        db.session.delete(row)
        with self.assertRaises(ReviewHistoryImmutable):
            db.session.commit()
        db.session.rollback()
        self.assessment.review_history.remove(row)
        with self.assertRaises(ReviewHistoryImmutable):
            db.session.commit()
        db.session.rollback()
        self.assertEqual(db.session.query(AssessmentReview).count(), 1)

    def test_session_bulk_dml_cannot_bypass_guards(self):
        self.seed_history()
        with self.assertRaises(ReviewWriteBlocked):
            db.session.execute(insert(AssessmentReview), self.fixture(sequence=2, from_state="returned_for_changes", to_state="pending_review"))
        for statement in (update(AssessmentReview).values(reason="replacement"), delete(AssessmentReview)):
            with self.assertRaises(ReviewHistoryImmutable):
                db.session.execute(statement)
        db.session.rollback()
        self.assertEqual(db.session.query(AssessmentReview).count(), 1)

    def test_database_rejects_invalid_transitions_sequences_and_links(self):
        for changes in ({"to_state": "unknown"}, {"from_state": "approved", "to_state": "pending_review"}, {"to_state": "pending_review"}, {"sequence": 0}, {"sequence": -1}, {"assessment_id": 999}, {"actor_user_id": 999}, {"actor_user_id": None}):
            with self.assertRaises(IntegrityError):
                with db.engine.begin() as connection:
                    connection.execute(insert(AssessmentReview.__table__), self.fixture(**changes))

    def test_duplicate_history_sequence_and_parent_deletion_rejected(self):
        self.seed_history()
        with self.assertRaises(IntegrityError):
            self.seed_history()
        for obj in (self.assessment, self.users["doctor"]):
            db.session.delete(obj)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()
        self.assertEqual(db.session.query(AssessmentReview).count(), 1)

    def test_migration_preserves_assessments_without_inventing_decisions(self):
        assessment_id = self.assessment.id
        with db.engine.begin() as connection:
            command.downgrade(migration_config(connection), "0003_assessment_inputs")
            self.assertNotIn("assessment_reviews", inspect(connection).get_table_names())
            command.upgrade(migration_config(connection), "head")
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM assessment_reviews").scalar(), 0)
            self.assertEqual(connection.exec_driver_sql("SELECT id FROM clinical_assessments").scalar(), assessment_id)
        db.session.expire_all()
        self.assertEqual(self.assessment.review_state, "pending_review")

    def test_mysql_offline_migration_defines_review_constraints(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+pymysql://test:dummy@127.0.0.1/example"}):
            command.upgrade(migration_config(output=output), "head", sql=True)
        sql = output.getvalue()
        self.assertIn("CREATE TABLE assessment_reviews", sql)
        self.assertIn("uq_review_assessment_sequence", sql)
        self.assertIn("ck_review_transition", sql)


if __name__ == "__main__":
    unittest.main()
