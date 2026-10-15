"""Owner-only patient/assessment APIs, real persistence, no model execution."""

import ast
import io
import json
import os
from pathlib import Path
import secrets
import unittest
from unittest.mock import patch

from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app import create_app
from backend.app.auth.security import hash_password, issue_token
from backend.app.database import db
from backend.app.models import ClinicalAssessment, Patient, User
from backend.app.api.assessment_validation import CATEGORICAL_INPUTS, NUMERIC_INPUTS, INPUT_FEATURES, OUTPUT_TARGETS
from test_database import migration_config


ROOT = Path(__file__).resolve().parents[2]


def valid_payload():
    # Type fixtures only: deliberately not a clinical or inference-validity claim.
    return {"inputs": {**{name: "fixture" for name in CATEGORICAL_INPUTS},
                       **{name: 1.5 for name in NUMERIC_INPUTS}}, "notes": "manual fixture"}


class PatientApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("isolated-fixture-password")

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
        for name, role_id in (("owner", 1), ("other", 1), ("doctor", 2), ("admin", 3), ("legacy", 1)):
            user = User(email=name + "@example.invalid", role_id=role_id, password_hash=self.password_hash)
            db.session.add(user)
            self.users[name] = user
        db.session.flush()
        self.patient = Patient(owner_user_id=self.users["owner"].id)
        self.other_patient = Patient(owner_user_id=self.users["other"].id)
        db.session.add_all([self.patient, self.other_patient])
        db.session.commit()
        self.headers = {name: {"Authorization": "Bearer " + issue_token(user)} for name, user in self.users.items()}
        self.client = self.app.test_client()
        self.url = f"/api/patients/{self.patient.id}/assessments"
        self.other_url = f"/api/patients/{self.other_patient.id}/assessments"

    def create_assessment(self, payload=None, actor="owner", url=None):
        return self.client.post(url or self.url, json=valid_payload() if payload is None else payload, headers=self.headers[actor])

    def operations(self):
        return [("POST", "/api/patients", {}), ("GET", "/api/patients/me", None),
                ("GET", f"/api/patients/{self.patient.id}", None),
                ("POST", self.url, valid_payload()), ("GET", self.url, None),
                ("GET", self.url + "/1", None)]

    def test_create_and_retrieve_legacy_profile(self):
        response = self.client.post("/api/patients", json={}, headers=self.headers["legacy"])
        self.assertEqual(response.status_code, 201)
        data = response.get_json()["patient"]
        self.assertEqual(data["owner_user_id"], self.users["legacy"].id)
        for url in ("/api/patients/me", f"/api/patients/{data['id']}"):
            self.assertEqual(self.client.get(url, headers=self.headers["legacy"]).get_json()["patient"], data)
        db.session.expire_all()
        self.assertEqual(db.session.get(Patient, data["id"]).owner_user_id, self.users["legacy"].id)

    def test_registration_profile_is_reused(self):
        response = self.client.post("/api/auth/register", json={"email": "new@example.invalid", "password": "new-fixture-password"})
        self.assertEqual(response.status_code, 201)
        login = self.client.post("/api/auth/login", json={"email": "new@example.invalid", "password": "new-fixture-password"})
        headers = {"Authorization": "Bearer " + login.get_json()["access_token"]}
        self.assertEqual(self.client.get("/api/patients/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/patients", json={}, headers=headers).status_code, 409)

    def test_duplicate_profile_and_unique_constraint(self):
        self.assertEqual(self.client.post("/api/patients", json={}, headers=self.headers["owner"]).status_code, 409)
        self.assertEqual(db.session.query(Patient).count(), 2)
        db.session.add(Patient(owner_user_id=self.users["owner"].id))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_profile_creation_rejects_client_owner_and_demographics(self):
        for data in ({"owner_user_id": self.users["other"].id}, {"id": 9}, {"role": "doctor"}, {"name": "fixture"}, [], None):
            with self.subTest(data=data):
                self.assertEqual(self.client.post("/api/patients", json=data, headers=self.headers["legacy"]).status_code, 400)
        self.assertEqual(db.session.query(Patient).count(), 2)

    def test_missing_self_profile_returns_404(self):
        self.assertEqual(self.client.get("/api/patients/me", headers=self.headers["legacy"]).status_code, 404)

    def test_all_routes_require_authentication(self):
        for method, url, data in self.operations():
            with self.subTest(method=method, url=url):
                response = self.client.open(url, method=method, json=data)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"]["message"], "Unauthorized")
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")

    def test_doctor_and_administrator_denied_every_read_and_write(self):
        self.create_assessment()
        for actor in ("doctor", "admin"):
            for method, url, data in self.operations():
                with self.subTest(actor=actor, method=method, url=url):
                    response = self.client.open(url, method=method, json=data, headers=self.headers[actor])
                    self.assertEqual(response.status_code, 403)
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 1)

    def test_cross_patient_and_nonexistent_ids_are_indistinguishable(self):
        assessment_id = self.create_assessment().get_json()["assessment"]["id"]
        for url in (f"/api/patients/{self.patient.id}", self.url, self.url + f"/{assessment_id}"):
            response = self.client.get(url, headers=self.headers["other"])
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json(), {"error": {"code": 404, "message": "Not Found"}})
        self.assertEqual(self.create_assessment(actor="other").status_code, 404)
        self.assertEqual(self.client.get("/api/patients/999999", headers=self.headers["owner"]).status_code, 404)
        self.assertEqual(self.client.get("/api/patients/999999999999999999999999999999", headers=self.headers["owner"]).status_code, 404)
        self.assertEqual(self.client.get(self.url + "/999999999999999999999999999999", headers=self.headers["owner"]).status_code, 404)
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 1)

    def test_assessment_cannot_be_read_via_another_owned_patient_path(self):
        own = self.create_assessment().get_json()["assessment"]["id"]
        other = self.create_assessment(actor="other", url=self.other_url).get_json()["assessment"]["id"]
        self.assertEqual(self.client.get(self.url + f"/{other}", headers=self.headers["owner"]).status_code, 404)
        self.assertEqual(self.client.get(self.other_url + f"/{own}", headers=self.headers["other"]).status_code, 404)

    def test_assessment_roundtrip_and_actor_from_authentication(self):
        payload = valid_payload()
        response = self.create_assessment(payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()["assessment"]
        self.assertEqual(data["patient_id"], self.patient.id)
        self.assertEqual(data["recorded_by_user_id"], self.users["owner"].id)
        self.assertEqual(data["inputs"], payload["inputs"])
        self.assertEqual(data["notes"], payload["notes"])
        self.assertIsNotNone(data["created_at"])
        db.session.remove()
        persisted = db.session.get(ClinicalAssessment, data["id"])
        self.assertEqual(persisted.inputs, payload["inputs"])
        self.assertEqual(persisted.recorded_by_user_id, self.users["owner"].id)
        fetched = self.client.get(self.url + f"/{data['id']}", headers=self.headers["owner"])
        self.assertEqual(fetched.get_json()["assessment"], data)
        self.assertEqual(self.client.get(self.url, headers=self.headers["owner"]).get_json()["assessments"], [data])
        self.assertNotIn("password", response.get_data(as_text=True))
        self.assertNotIn("access_token", response.get_data(as_text=True))
        self.assertEqual(set(data), {"id", "patient_id", "recorded_by_user_id", "created_at", "inputs", "notes"})

    def test_explicit_zero_preserved_and_missing_values_never_default(self):
        payload = valid_payload()
        payload["inputs"]["BP Systolic"] = 0
        self.assertEqual(self.create_assessment(payload).get_json()["assessment"]["inputs"]["BP Systolic"], 0)
        del payload["inputs"]["Pulse Rate"]
        self.assertEqual(self.create_assessment(payload).status_code, 400)
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 1)

    def test_all_twelve_inputs_are_required_with_exact_names(self):
        for key in INPUT_FEATURES:
            payload = valid_payload()
            del payload["inputs"][key]
            with self.subTest(key=key):
                self.assertEqual(self.create_assessment(payload).status_code, 400)
        for extra in ("Weight", "stress_levels", "Symptoms", "Herbal Therapy Strategy"):
            payload = valid_payload()
            payload["inputs"][extra] = "fixture"
            self.assertEqual(self.create_assessment(payload).status_code, 400)
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 0)

    def test_categorical_and_numeric_type_validation(self):
        for name in CATEGORICAL_INPUTS:
            for value in (None, 1, [], {}, "", "   ", "x" * 257, "\x00", "\ud800"):
                payload = valid_payload()
                payload["inputs"][name] = value
                self.assertEqual(self.create_assessment(payload).status_code, 400)
        for name in NUMERIC_INPUTS:
            for value in (None, True, False, "1", [], {}, float("nan"), float("inf"), -float("inf"), 10 ** 400):
                payload = valid_payload()
                payload["inputs"][name] = value
                self.assertEqual(self.create_assessment(payload).status_code, 400)
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 0)

    def test_envelope_notes_and_server_owned_fields_validation(self):
        for data in ({}, {"inputs": None}, {"inputs": []}, {"inputs": {}}, [], None):
            self.assertEqual(self.client.post(self.url, json=data, headers=self.headers["owner"]).status_code, 400)
        for key in ("id", "patient_id", "recorded_by_user_id", "created_at", "outputs", "role"):
            payload = valid_payload()
            payload[key] = 1
            self.assertEqual(self.create_assessment(payload).status_code, 400)
        for notes in (1, [], {}, "x" * 4097, "\x00", "\ud800"):
            payload = valid_payload()
            payload["notes"] = notes
            self.assertEqual(self.create_assessment(payload).status_code, 400)

    def test_optional_notes_are_null_without_clinical_defaults(self):
        payload = valid_payload()
        del payload["notes"]
        data = self.create_assessment(payload).get_json()["assessment"]
        self.assertIsNone(data["notes"])
        self.assertEqual(data["inputs"], payload["inputs"])

    def test_malformed_duplicate_and_oversized_json(self):
        for raw in ("{", "null", '{"inputs":{},"inputs":{}}', json.dumps(valid_payload()).replace('"BP Systolic": 1.5', '"BP Systolic": 1.5, "BP Systolic": 2')):
            self.assertEqual(self.client.post(self.url, data=raw, content_type="application/json", headers=self.headers["owner"]).status_code, 400)
        self.assertEqual(self.client.post(self.url, data="x" * 17000, content_type="application/json", headers=self.headers["owner"]).status_code, 413)
        self.assertEqual(self.client.post(self.url, data=json.dumps(valid_payload()), content_type="text/plain", headers=self.headers["owner"]).status_code, 400)

    def test_list_pagination_is_bounded_and_patient_scoped(self):
        ids = [self.create_assessment().get_json()["assessment"]["id"] for _ in range(3)]
        self.create_assessment(actor="other", url=self.other_url)
        first = self.client.get(self.url + "?limit=2", headers=self.headers["owner"]).get_json()
        self.assertEqual([row["id"] for row in first["assessments"]], ids[:2])
        self.assertEqual(first["next_after_id"], ids[1])
        last = self.client.get(self.url + f"?limit=2&after_id={ids[1]}", headers=self.headers["owner"]).get_json()
        self.assertEqual([row["id"] for row in last["assessments"]], ids[2:])
        self.assertIsNone(last["next_after_id"])
        empty = self.client.get(self.url + "?after_id=999", headers=self.headers["owner"]).get_json()
        self.assertEqual(empty, {"assessments": [], "next_after_id": None})

    def test_invalid_pagination(self):
        for query in ("limit=0", "limit=101", "limit=bad", "after_id=-1", "after_id=bad", "after_id=999999999999999999999", "limit=1&limit=2", "owner_user_id=2"):
            self.assertEqual(self.client.get(self.url + "?" + query, headers=self.headers["owner"]).status_code, 400)

    def test_no_store_on_success_and_denials(self):
        for actor in ("owner", "other", "doctor", "admin"):
            response = self.client.get(self.url, headers=self.headers[actor])
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_failed_assessment_commit_rolls_back_without_sensitive_logs(self):
        with patch.object(self.app.logger, "error") as logger, patch.object(db.session, "commit", side_effect=OperationalError("private-note", {}, Exception("private-note"))):
            response = self.create_assessment()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-note", response.get_data(as_text=True))
        logger.assert_not_called()
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 0)
        self.assertEqual(self.create_assessment().status_code, 201)

    def test_profile_race_rolls_back(self):
        with patch.object(db.session, "commit", side_effect=IntegrityError("private", {}, Exception("private"))):
            response = self.client.post("/api/patients", json={}, headers=self.headers["legacy"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(db.session.query(Patient).count(), 2)

    def test_legacy_assessments_keep_null_inputs(self):
        row = ClinicalAssessment(patient_id=self.patient.id, recorded_by_user_id=self.users["doctor"].id, notes="legacy fixture")
        db.session.add(row)
        db.session.commit()
        data = self.client.get(self.url + f"/{row.id}", headers=self.headers["owner"]).get_json()["assessment"]
        self.assertIsNone(data["inputs"])
        self.assertEqual(data["recorded_by_user_id"], self.users["doctor"].id)
        self.assertEqual(self.client.get(self.url + f"/{row.id}", headers=self.headers["doctor"]).status_code, 403)

    def test_third_migration_preserves_legacy_records(self):
        with db.engine.begin() as connection:
            command.downgrade(migration_config(connection), "0002_password_hash")
            connection.exec_driver_sql("INSERT INTO clinical_assessments (patient_id, recorded_by_user_id, notes) VALUES (?, ?, ?)", (self.patient.id, self.users["doctor"].id, "legacy fixture"))
            command.upgrade(migration_config(connection), "head")
            self.assertIsNone(connection.exec_driver_sql("SELECT inputs FROM clinical_assessments").scalar())
            command.downgrade(migration_config(connection), "0002_password_hash")
            self.assertNotIn("inputs", {column["name"] for column in inspect(connection).get_columns("clinical_assessments")})
            command.upgrade(migration_config(connection), "head")

    def test_feature_and_output_names_match_frozen_source_without_importing_it(self):
        source = ast.parse((ROOT / "ml/source/AyurSage_Training_v17.py").read_text(encoding="utf-8"))
        constants = {}
        for node in source.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"CATEGORICAL_COLS", "NUMERIC_COLS", "OUTPUT_TARGETS"}:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
        self.assertEqual(list(CATEGORICAL_INPUTS), constants["CATEGORICAL_COLS"])
        self.assertEqual(list(NUMERIC_INPUTS), constants["NUMERIC_COLS"])
        self.assertEqual(list(OUTPUT_TARGETS), constants["OUTPUT_TARGETS"])

    def test_mysql_offline_migration_has_json_column(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+pymysql://test:dummy@127.0.0.1/example"}):
            command.upgrade(migration_config(output=output), "head", sql=True)
        self.assertIn("ADD COLUMN inputs JSON", output.getvalue())


if __name__ == "__main__":
    unittest.main()
