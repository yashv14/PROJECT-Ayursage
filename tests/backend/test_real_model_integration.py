"""End-to-end integration test for the real V17 ML model with Flask backend.

No Docker or external supervisor: verifies in-process model loading and inference.
"""

import os
import secrets
import unittest
from io import BytesIO

from alembic import command
from alembic.config import Config

from backend.app import create_app
from backend.app.auth.security import hash_password, issue_token
from backend.app.database import db
from backend.app.models import Patient, User
from backend.app.services.v17 import V17Service
from tests.backend.test_database import migration_config


VALID_SAMPLE_INPUTS = {
    "Disease": "Melioidosis",
    "Symptom Severity": "Mild",
    "Nadi Reading": "Vata-Kapha",
    "Constitution/Prakriti": "Vata-Kapha",
    "Stress Levels": "Low Stress",
    "Sleep Patterns": "Regular Sleep",
    "Age Group": "20-40",
    "Physical Activity Levels": "High",
    "BP Systolic": 120.0,
    "BP Diastolic": 80.0,
    "Pulse Rate": 72.0,
    "Weight (kg)": 65.0,
}


class RealModelInferenceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Verify V17Service loads the real .pkl artifact
        cls.service = V17Service(loading_enabled=True)
        cls.service.load()

    def test_direct_model_prediction(self):
        result = self.service.predict(VALID_SAMPLE_INPUTS)
        self.assertEqual(result["model_version"], "AyurSage_v17")
        self.assertEqual(result["status"], "pending_clinical_review")
        self.assertFalse(result["persisted"])
        outputs = result["outputs"]
        self.assertIn("Herbal Therapy Strategy", outputs)
        self.assertIn("Lifestyle Recommendations", outputs)
        self.assertIn("Therapeutic Yoga Module", outputs)
        self.assertIn("Follow-up Recommendation", outputs)
        for key, val in outputs.items():
            self.assertTrue(isinstance(val, str) and len(val) > 0)

    def test_flask_endpoint_with_real_prediction(self):
        # Set up an in-memory SQLite app with real model loading enabled
        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": secrets.token_urlsafe(48),
            "V17_MODEL_LOADING_ENABLED": True,
        })
        with app.app_context():
            with db.engine.begin() as connection:
                command.upgrade(migration_config(connection), "head")
            app.extensions["v17"].load()

            user = User(email="patient_ml@example.com", password_hash=hash_password("Pass1234!"), role_id=1)
            db.session.add(user)
            db.session.commit()
            patient = Patient(owner_user_id=user.id)
            db.session.add(patient)
            db.session.commit()
            token = issue_token(user)

            client = app.test_client()
            resp = client.post(
                f"/api/patients/{patient.id}/assessments",
                headers={"Authorization": f"Bearer {token}"},
                json={"inputs": VALID_SAMPLE_INPUTS, "notes": "Feeling good", "predict": True},
            )
            self.assertEqual(resp.status_code, 201)
            data = resp.get_json()
            self.assertIn("assessment", data)
            self.assertIn("prediction", data)
            self.assertEqual(data["prediction"]["model_version"], "AyurSage_v17")
            self.assertIn("Herbal Therapy Strategy", data["prediction"]["outputs"])
