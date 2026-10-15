"""Real JWT/hash and isolated migration tests; extra RBAC routes exist only here."""

from datetime import datetime, timezone
import io
import os
import secrets
import unittest
from unittest.mock import patch

import jwt
from alembic import command
from flask import Blueprint, g
from sqlalchemy import select, inspect
from sqlalchemy.exc import OperationalError, IntegrityError
from werkzeug.exceptions import Unauthorized

from backend.app import create_app
from backend.app.database import db
from backend.app.models import User, Patient
from backend.app.auth.security import roles_required, auth_required, require_patient_owner, hash_password, verify_password
from test_database import migration_config


PASSWORD = "test-password-strong-123"


class AuthTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.secret = secrets.token_urlsafe(48)
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "JWT_SECRET_KEY": self.secret})
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        with db.engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")
        bp = Blueprint("test_permissions", __name__)
        for role in ("patient", "doctor", "admin", "receptionist"):
            def permitted():
                return {"ok": True}
            bp.add_url_rule("/test/" + role, role, roles_required(role)(permitted))

        @bp.get("/test/owner/<int:patient_id>")
        @auth_required
        def owned(patient_id):
            require_patient_owner(db.session.get(Patient, patient_id))
            return {"ok": True}

        self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def register(self, email="patient@example.invalid", password=PASSWORD, **extra):
        return self.client.post("/api/auth/register", json={"email": email, "password": password, **extra})

    def login(self, email="patient@example.invalid", password=PASSWORD):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def headers(self, email="patient@example.invalid"):
        return {"Authorization": "Bearer " + self.login(email).get_json()["access_token"]}

    def signed(self, **changes):
        now = int(datetime.now(timezone.utc).timestamp())
        payload = {"sub": "1", "iat": now, "nbf": now, "exp": now + 300, "iss": "ayur-sage", "aud": "ayur-sage-api", "jti": "fixture", "token_type": "access"}
        payload.update(changes)
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def test_registration_hash_and_patient_profile(self):
        response = self.register(" Patient@Example.invalid ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["user"]["role"], "patient")
        user = db.session.scalar(select(User))
        self.assertEqual(user.email, "patient@example.invalid")
        self.assertNotEqual(user.password_hash, PASSWORD)
        self.assertNotIn(PASSWORD, user.password_hash)
        self.assertTrue(user.password_hash.startswith("scrypt:32768:8:1$"))
        self.assertTrue(verify_password(user.password_hash, PASSWORD))
        self.assertEqual(user.patient.owner_user_id, user.id)
        self.assertNotIn("password", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_login_and_me(self):
        self.register()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["expires_in"], 900)
        claims = jwt.decode(data["access_token"], self.secret, algorithms=["HS256"], audience="ayur-sage-api", issuer="ayur-sage")
        self.assertEqual(claims["exp"] - claims["iat"], 900)
        self.assertNotIn("email", claims)
        self.assertNotIn("role", claims)
        me = self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + data["access_token"]})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["email"], "patient@example.invalid")
        self.assertEqual(set(me.get_json()["user"]), {"id", "email", "role"})

    def test_incorrect_credentials_identical_responses(self):
        self.register()
        wrong = self.login(password="wrong")
        missing = self.login(email="missing@example.invalid")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.get_json(), missing.get_json())
        self.assertEqual(wrong.headers["WWW-Authenticate"], "Bearer")

    def test_duplicate_case_normalized_registration(self):
        self.register()
        self.assertEqual(self.register("PATIENT@example.invalid").status_code, 409)
        self.assertEqual(db.session.query(User).count(), 1)
        self.assertEqual(db.session.query(Patient).count(), 1)

    def test_no_public_privileged_assignment(self):
        for extra in ({"role": "doctor"}, {"role": "admin"}, {"role": "patient"}, {"role_id": 2}, {"password_hash": "attacker"}):
            with self.subTest(extra=extra):
                self.assertEqual(self.register(**extra).status_code, 400)
        self.assertEqual(db.session.query(User).count(), 0)

    def test_input_validation(self):
        for data in (None, [], {}, {"email": "invalid", "password": PASSWORD}, {"email": 1, "password": PASSWORD}, {"email": "patient@example.invalid", "password": "short"}, {"email": "patient@example.invalid", "password": 123}, {"email": "patient@example.invalid", "password": "x" * 129}):
            with self.subTest(data=data):
                response = self.client.post("/api/auth/register", json=data)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/auth/register", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/auth/register", data="x" * 5000, content_type="application/json").status_code, 413)

    def test_missing_and_malformed_jwts(self):
        for header in (None, "", "Basic xyz", "Bearer", "Bearer a b", "Bearer garbage", "Bearer " + "x" * 4097):
            with self.subTest(header=header):
                response = self.client.get("/api/auth/me", headers={} if header is None else {"Authorization": header})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json(), {"error": {"code": 401, "message": "Unauthorized"}})

    def test_invalid_expired_claims_and_wrong_signatures(self):
        self.register()
        now = int(datetime.now(timezone.utc).timestamp())
        tokens = [self.signed(exp=now - 1), self.signed(nbf=now + 999), self.signed(iss="other"), self.signed(aud="other"), self.signed(sub="bogus"), self.signed(sub="999"), self.signed(token_type="refresh"), self.signed(exp=None), jwt.encode({"sub": "1"}, self.secret, algorithm="HS256"), jwt.encode({"sub": "1"}, secrets.token_urlsafe(48), algorithm="HS256"), jwt.encode({"sub": "1"}, "", algorithm="none")]
        tokens.extend([self.signed(exp=float("inf")), self.signed(iat=float("inf"))])
        for token in tokens:
            with self.subTest(token_index=tokens.index(token)):
                self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code, 401)

    def test_all_role_permissions_and_cli_provisioning(self):
        self.register()
        runner = self.app.test_cli_runner()
        for role in ("doctor", "admin", "receptionist"):
            result = runner.invoke(args=["create-privileged-user", "--email", role + "@example.invalid", "--role", role], input=PASSWORD + "\n" + PASSWORD + "\n")
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn(PASSWORD, result.output)
            user = db.session.scalar(select(User).where(User.email == role + "@example.invalid"))
            self.assertEqual(user.role.code, role)
            self.assertIsNone(user.patient)
            self.assertTrue(verify_password(user.password_hash, PASSWORD))
        for role in ("patient", "doctor", "admin", "receptionist"):
            headers = self.headers(role + "@example.invalid")
            for allowed in ("patient", "doctor", "admin"):
                with self.subTest(actor=role, required=allowed):
                    self.assertEqual(self.client.get("/test/" + allowed, headers=headers).status_code, 200 if role == allowed else 403)
        self.assertEqual(self.client.get("/test/admin").status_code, 401)

    def test_cli_rejects_duplicate_invalid_and_uncontrolled_roles(self):
        runner = self.app.test_cli_runner()
        args = ["create-privileged-user", "--email", "doctor@example.invalid", "--role", "doctor"]
        self.assertEqual(runner.invoke(args=args, input=PASSWORD + "\n" + PASSWORD + "\n").exit_code, 0)
        duplicate = runner.invoke(args=args, input=PASSWORD + "\n" + PASSWORD + "\n")
        self.assertNotEqual(duplicate.exit_code, 0)
        self.assertNotIn(PASSWORD, duplicate.output)
        self.assertNotEqual(runner.invoke(args=["create-privileged-user", "--email", "p@example.invalid", "--role", "patient"]).exit_code, 0)
        self.assertNotEqual(runner.invoke(args=args, input="short\nshort\n").exit_code, 0)

    def test_ownership_denies_nonowners_and_privileged_roles(self):
        self.register()
        self.register("other@example.invalid")
        owner_id = db.session.scalar(select(Patient.id).join(User).where(User.email == "patient@example.invalid"))
        self.assertEqual(self.client.get(f"/test/owner/{owner_id}", headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.get(f"/test/owner/{owner_id}", headers=self.headers("other@example.invalid")).status_code, 403)
        for role in ("doctor", "admin"):
            user = User(email=role + "@example.invalid", role_id=2 if role == "doctor" else 3, password_hash=hash_password(PASSWORD))
            db.session.add(user)
            db.session.commit()
            self.assertEqual(self.client.get(f"/test/owner/{owner_id}", headers=self.headers(user.email)).status_code, 403)
        with self.app.test_request_context():
            g.pop("current_user", None)
            with self.assertRaises(Unauthorized):
                require_patient_owner(None)

    def test_database_role_changes_take_effect_for_existing_token(self):
        self.register()
        headers = self.headers()
        user = db.session.scalar(select(User))
        user.role_id = 2
        db.session.commit()
        db.session.expire_all()
        self.assertEqual(self.client.get("/test/patient", headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/test/doctor", headers=headers).status_code, 200)

    def test_passwordless_and_removed_users_cannot_authenticate(self):
        user = User(email="legacy@example.invalid", role_id=1)
        db.session.add(user)
        db.session.commit()
        self.assertEqual(self.login(user.email).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + self.signed(sub=str(user.id))}).status_code, 401)
        db.session.delete(user)
        db.session.commit()
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + self.signed(sub=str(user.id))}).status_code, 401)

    def test_database_failure_is_generic_and_rolls_back(self):
        with patch.object(self.app.logger, "error") as error_log, patch.object(db.session, "scalars", side_effect=OperationalError("sensitive-email", {}, Exception(PASSWORD))), patch.object(db.session, "rollback") as rollback:
            response = self.login()
        error_log.assert_not_called()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(PASSWORD, response.get_data(as_text=True))
        rollback.assert_called_once()

    def test_registration_commit_race_rolls_back(self):
        with patch.object(db.session, "commit", side_effect=IntegrityError("sensitive", {}, Exception(PASSWORD))):
            response = self.register()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(db.session.query(User).count(), 0)
        self.assertEqual(db.session.query(Patient).count(), 0)

    def test_password_hash_salts_and_malformed_hashes(self):
        first, second = hash_password(PASSWORD), hash_password(PASSWORD)
        self.assertNotEqual(first, second)
        self.assertFalse(verify_password(first, "wrong"))
        self.assertFalse(verify_password(None, PASSWORD))
        self.assertFalse(verify_password("broken", PASSWORD))

    def test_second_migration_preserves_legacy_rows_and_downgrades(self):
        with db.engine.begin() as connection:
            command.downgrade(migration_config(connection), "0001_database_foundation")
            connection.exec_driver_sql("INSERT INTO users (email, role_id) VALUES ('legacy@example.invalid', 1)")
            command.upgrade(migration_config(connection), "head")
            self.assertIsNone(connection.exec_driver_sql("SELECT password_hash FROM users").scalar())
            command.downgrade(migration_config(connection), "0001_database_foundation")
            self.assertNotIn("password_hash", {column["name"] for column in inspect(connection).get_columns("users")})
            command.upgrade(migration_config(connection), "head")


class AuthConfigurationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_missing_configuration_denies_auth_but_preserves_health(self):
        app = create_app({"TESTING": True})
        self.assertEqual(app.test_client().get("/api/health").status_code, 200)
        self.assertEqual(app.test_client().get("/api/auth/me").status_code, 503)
        self.assertEqual(app.test_client().post("/api/auth/register", json={"email": "p@example.invalid", "password": PASSWORD}).status_code, 503)
        result = app.test_cli_runner().invoke(args=["create-privileged-user", "--email", "d@example.invalid", "--role", "doctor"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Service Unavailable", result.output)

    def test_invalid_secrets_and_expiry_are_rejected_safely(self):
        for secret in ("short-private-secret", "x" * 64):
            with self.assertRaises(ValueError) as caught:
                create_app({"JWT_SECRET_KEY": secret})
            self.assertNotIn(secret, str(caught.exception))
        for expiry in ("invalid-private-value", 0, 59, 86401, True, 60.5):
            with self.assertRaisesRegex(ValueError, "JWT_ACCESS_TOKEN_SECONDS must be"):
                create_app({"JWT_ACCESS_TOKEN_SECONDS": expiry})

    def test_environment_secret_and_expiry(self):
        secret = secrets.token_urlsafe(48)
        with patch.dict(os.environ, {"JWT_SECRET_KEY": secret, "JWT_ACCESS_TOKEN_SECONDS": "600"}):
            app = create_app()
        self.assertEqual(app.config["JWT_SECRET_KEY"], secret)
        self.assertEqual(app.config["JWT_ACCESS_TOKEN_SECONDS"], 600)
        self.assertEqual(app.test_client().get("/api/auth/me").status_code, 503)

    def test_unknown_role_decorator_is_configuration_error(self):
        with self.assertRaises(ValueError):
            roles_required("administrator")


if __name__ == "__main__":
    unittest.main()
