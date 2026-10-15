"""Isolated persistence tests: real Alembic migrations, no cloud or auth."""

import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.app import create_app
from backend.app.database import db, validate_database_url
from backend.app.models import ClinicalAssessment, Patient, Role, User, ROLE_CODES


ROOT = Path(__file__).resolve().parents[2]


def migration_config(connection=None, output=None):
    config = Config(str(ROOT / "backend/alembic.ini"), output_buffer=output)
    if connection is not None:
        config.attributes["connection"] = connection
    return config


class DatabaseConfigurationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_absent_and_blank_url_disable_database(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                if value is not None:
                    os.environ["DATABASE_URL"] = value
                app = create_app({"TESTING": True})
                self.assertNotIn("sqlalchemy", app.extensions)
                self.assertIsNone(app.config["SQLALCHEMY_DATABASE_URI"])
                self.assertEqual(app.test_client().get("/api/health").status_code, 200)

    def test_environment_and_test_override(self):
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+pymysql://test:dummy@127.0.0.1/example"}):
            app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        with app.app_context():
            self.assertEqual(db.engine.dialect.name, "sqlite")
            self.assertEqual(inspect(db.engine).get_table_names(), [])
            db.engine.dispose()

    def test_mysql_configuration_does_not_connect_at_startup(self):
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+pymysql://test:dummy@127.0.0.1/example"}), patch("pymysql.connect", side_effect=AssertionError("unexpected connection")):
            app = create_app()
            self.assertEqual(app.test_client().get("/api/health").status_code, 200)
            with app.app_context():
                self.assertEqual(db.engine.dialect.name, "mysql")
                db.engine.dispose()

    def test_invalid_urls_fail_without_echoing_credentials(self):
        for value in ("private-invalid-value", "postgresql://test:private-secret@host/db", "sqlite:///relative.db", "sqlite://test:private-secret@host/C:/test.sqlite", "mysql://test:private-secret@host/db", "sqlite://", "mysql+pymysql://host"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"DATABASE_URL": value}):
                    with self.assertRaises(ValueError) as caught:
                        create_app()
                self.assertNotIn(value, str(caught.exception))
                self.assertNotIn("private-secret", str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def test_migrations_require_explicit_url(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL is required"):
            command.upgrade(migration_config(), "head")

    def test_file_database_environment_migrations(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            filename = Path(directory) / "isolated.sqlite"
            url = "sqlite:///" + filename.as_posix()
            self.assertEqual(validate_database_url(url).database, filename.as_posix())
            with patch.dict(os.environ, {"DATABASE_URL": url}):
                command.upgrade(migration_config(), "head")
                app = create_app()
                with app.app_context():
                    self.assertEqual(db.session.scalars(select(Role.code).order_by(Role.id)).all(), list(ROLE_CODES))
                    db.session.remove()
                    db.engine.dispose()
                command.downgrade(migration_config(), "base")

    def test_offline_mysql_migration_sql(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+pymysql://test:dummy@127.0.0.1/example"}):
            command.upgrade(migration_config(output=output), "head", sql=True)
        sql = output.getvalue()
        self.assertIn("CREATE TABLE clinical_assessments", sql)
        self.assertIn("ENGINE=InnoDB", sql)
        self.assertIn("ON DELETE RESTRICT", sql)
        self.assertIn("ADD COLUMN password_hash VARCHAR(512)", sql)
        self.assertNotIn("dummy", sql)


class DatabaseModelTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        with db.engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")

    def seed_relationships(self):
        patient_role = db.session.get(Role, 1)
        doctor_role = db.session.get(Role, 2)
        owner = User(email="patient@example.invalid", role=patient_role)
        doctor = User(email="doctor@example.invalid", role=doctor_role)
        patient = Patient(owner=owner)
        assessment = ClinicalAssessment(patient=patient, recorded_by=doctor, notes="Manual fixture")
        db.session.add_all([owner, doctor, patient, assessment])
        db.session.commit()
        return owner, doctor, patient, assessment

    def assert_rejected(self, obj):
        db.session.add(obj)
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_relationships_and_required_roles(self):
        owner, doctor, patient, assessment = self.seed_relationships()
        db.session.expire_all()
        self.assertEqual(owner.role.code, "patient")
        self.assertEqual(doctor.role.code, "doctor")
        self.assertEqual(db.session.get(Role, 3).code, "admin")
        self.assertEqual(owner.patient, patient)
        self.assertEqual(patient.owner, owner)
        self.assertEqual(patient.assessments, [assessment])
        self.assertEqual(doctor.assessments, [assessment])
        self.assertEqual(assessment.recorded_by, doctor)
        self.assertIsNotNone(assessment.created_at)

    def test_unique_email_and_patient_owner(self):
        owner, _, _, _ = self.seed_relationships()
        self.assert_rejected(User(email=owner.email, role_id=1))
        self.assert_rejected(Patient(owner_user_id=owner.id))

    def test_role_constraints(self):
        self.assert_rejected(Role(code="unsupported"))
        self.assert_rejected(Role(code="patient"))
        self.assert_rejected(Role(code=None))

    def test_required_columns(self):
        for obj in (User(role_id=1), User(email="missing-role@example.invalid"), Patient(), ClinicalAssessment()):
            with self.subTest(model=type(obj).__name__):
                self.assert_rejected(obj)

    def test_foreign_keys_are_enforced(self):
        _, doctor, patient, _ = self.seed_relationships()
        self.assertEqual(db.session.execute(text("PRAGMA foreign_keys")).scalar(), 1)
        for obj in (User(email="bad-role@example.invalid", role_id=999), Patient(owner_user_id=999), ClinicalAssessment(patient_id=999, recorded_by_user_id=doctor.id), ClinicalAssessment(patient_id=patient.id, recorded_by_user_id=999)):
            with self.subTest(model=type(obj).__name__):
                self.assert_rejected(obj)

    def test_deletion_cannot_orphan_records(self):
        owner, doctor, patient, _ = self.seed_relationships()
        for obj in (owner, doctor, patient, owner.role):
            with self.subTest(model=type(obj).__name__):
                db.session.delete(obj)
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()
        self.assertEqual(db.session.query(ClinicalAssessment).count(), 1)

    def test_failed_commit_can_be_rolled_back_and_reused(self):
        self.assert_rejected(User(email="invalid@example.invalid", role_id=999))
        valid = User(email="valid@example.invalid", role_id=1)
        db.session.add(valid)
        db.session.commit()
        self.assertIsNotNone(valid.id)

    def test_migration_matches_models_and_is_repeatable(self):
        with db.engine.begin() as connection:
            self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
            command.upgrade(migration_config(connection), "head")
        self.assertEqual(db.session.query(Role).count(), len(ROLE_CODES))

    def test_downgrade_and_reupgrade(self):
        with db.engine.begin() as connection:
            command.downgrade(migration_config(connection), "base")
            self.assertEqual(inspect(connection).get_table_names(), ["alembic_version"])
            command.upgrade(migration_config(connection), "head")
        self.assertEqual(db.session.query(Role).count(), len(ROLE_CODES))

    def test_separate_apps_have_isolated_databases(self):
        self.seed_relationships()
        second = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        with second.app_context():
            self.assertEqual(inspect(db.engine).get_table_names(), [])
            db.engine.dispose()
        self.assertEqual(db.session.query(User).count(), 2)

    def test_unmigrated_database_fails_without_affecting_health(self):
        second = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        with second.app_context():
            with self.assertRaises(OperationalError):
                db.session.execute(select(User)).all()
            db.session.rollback()
            self.assertEqual(second.test_client().get("/api/health").status_code, 200)
            db.session.remove()
            db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
