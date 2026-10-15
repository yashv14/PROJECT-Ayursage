"""Consent-attested grants through real migrated persistence and Flask routes."""
from datetime import timedelta
import io
import json
import os
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from backend.app.database import db
from backend.app.models import GrantAdministrator, PatientDoctorGrant, Role, User
from backend.app.auth.grants import utc_now
from backend.app.auth.security import issue_token
from test_database import migration_config
import test_patients as patient_tests
from test_patients import valid_payload


class AccessGrantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        patient_tests.PatientApiTests.setUpClass.__func__(cls)

    def setUp(self):
        patient_tests.PatientApiTests.setUp(self)
        self.issue_url = f"/api/patients/{self.patient.id}/doctor-access-grants"
        self.authorize_admin()

    def authorize_admin(self):
        db.session.add(GrantAdministrator(user_id=self.users["admin"].id, authorized_at=utc_now()))
        db.session.commit()

    def grant(self, actor="admin", reference="consent-record-001", **extra):
        payload = {"doctor_user_id": self.users["doctor"].id, "consent_reference": reference, **extra}
        return self.client.post(self.issue_url, json=payload, headers=self.headers[actor])

    def revoke(self, grant_id, actor="owner", patient_id=None):
        url = f"/api/patients/{patient_id or self.patient.id}/doctor-access-grants/{grant_id}/revoke"
        return self.client.post(url, json={}, headers=self.headers[actor])

    def assessment(self):
        return self.client.post(self.url, json=valid_payload(), headers=self.headers["owner"]).get_json()["assessment"]

    def test_default_denial_and_granted_reads_only(self):
        assessment = self.assessment()
        detail = self.url + f"/{assessment['id']}"
        for url in (self.url, detail):
            self.assertEqual(self.client.get(url, headers=self.headers["doctor"]).status_code, 403)
        response = self.grant()
        self.assertEqual(response.status_code, 201)
        data = response.get_json()["grant"]
        db.session.expire_all()
        row = db.session.get(PatientDoctorGrant, data["id"])
        self.assertEqual(row.expires_at - row.issued_at, timedelta(days=30))
        self.assertEqual(row.issuer_user_id, self.users["admin"].id)
        self.assertEqual(row.consent_owner_user_id, self.users["owner"].id)
        self.assertEqual(row.consent_reference, "consent-record-001")
        self.assertEqual(row.scope, "assessment_read")
        self.assertEqual(self.client.get(detail, headers=self.headers["doctor"]).get_json()["assessment"], assessment)
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).get_json()["assessments"], [assessment])
        for method, url, payload in (("GET", f"/api/patients/{self.patient.id}", None),
            ("GET", "/api/patients/me", None), ("POST", self.url, valid_payload()),
            ("POST", "/api/patients", {})):
            self.assertEqual(self.client.open(url, method=method, json=payload, headers=self.headers["doctor"]).status_code, 403)
        self.assertEqual(self.client.get(self.other_url, headers=self.headers["doctor"]).status_code, 403)
        self.assertEqual(self.client.get(self.url, headers=self.headers["admin"]).status_code, 403)
        self.assertEqual(self.client.get(detail, headers=self.headers["admin"]).status_code, 403)

    def test_owner_revoke_is_immediate_and_idempotent(self):
        assessment = self.assessment()
        row = self.grant().get_json()["grant"]
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 200)
        revoked = self.revoke(row["id"])
        self.assertEqual(revoked.status_code, 200)
        data = revoked.get_json()["grant"]
        self.assertEqual(data["status"], "revoked")
        self.assertEqual(data["revoked_by_user_id"], self.users["owner"].id)
        self.assertTrue(data["revoked_at"].endswith("Z"))
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 403)
        self.assertEqual(self.client.get(self.url + f"/{assessment['id']}", headers=self.headers["doctor"]).status_code, 403)
        self.assertEqual(self.revoke(row["id"], "admin").get_json()["grant"], data)
        self.assertEqual(self.client.get(self.url, headers=self.headers["owner"]).status_code, 200)

    def test_authorized_administrator_can_revoke(self):
        row = self.grant().get_json()["grant"]
        data = self.revoke(row["id"], "admin").get_json()["grant"]
        self.assertEqual(data["revoked_by_user_id"], self.users["admin"].id)
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 403)

    def test_expiry_checked_on_each_request_including_exact_boundary(self):
        assessment = self.assessment()
        now = utc_now()
        with patch("backend.app.api.access_grants.utc_now", return_value=now):
            row = self.grant().get_json()["grant"]
        expiry = now + timedelta(days=30)
        for instant, expected in ((now - timedelta(seconds=1), 403),
            (expiry - timedelta(seconds=1), 200), (expiry, 403), (expiry + timedelta(seconds=1), 403)):
            with patch("backend.app.auth.grants.utc_now", return_value=instant):
                self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, expected)
                self.assertEqual(self.client.get(self.url + f"/{assessment['id']}", headers=self.headers["doctor"]).status_code, expected)
        self.assertEqual(db.session.get(PatientDoctorGrant, row["id"]).status, "issued")

    def test_only_explicitly_authorized_admin_can_issue_or_revoke(self):
        row = self.grant().get_json()["grant"]
        for actor in ("owner", "other", "doctor", "legacy"):
            self.assertEqual(self.grant(actor).status_code, 403)
        self.assertEqual(self.revoke(row["id"], "doctor").status_code, 403)
        self.assertEqual(self.revoke(row["id"], "other").status_code, 404)
        self.assertEqual(self.revoke(row["id"], "owner", self.other_patient.id).status_code, 404)
        db.session.delete(db.session.get(GrantAdministrator, self.users["admin"].id))
        db.session.commit()
        self.assertEqual(self.grant().status_code, 403)
        self.assertEqual(self.revoke(row["id"], "admin").status_code, 403)
        self.assertEqual(self.client.get(self.issue_url, headers=self.headers["admin"]).status_code, 403)
        self.assertEqual(self.revoke(row["id"]).status_code, 200)

    def test_consent_and_server_fields_cannot_be_omitted_or_forged(self):
        for reference in (None, "", "   ", "x" * 257, "a\nb", "\x00"):
            self.assertEqual(self.grant(reference=reference).status_code, 400)
        for name, value in (("scope", "review"), ("expires_at", "2099-01-01"),
            ("issuer_user_id", self.users["owner"].id), ("status", "issued"),
            ("consent_owner_user_id", self.users["other"].id)):
            self.assertEqual(self.grant(**{name: value}).status_code, 400)
        for doctor_id in (True, "3", -1, 2147483648, self.users["owner"].id, self.users["admin"].id, 999):
            self.assertEqual(self.grant(doctor_user_id=doctor_id).status_code, 400)
        self.assertEqual(db.session.query(PatientDoctorGrant).count(), 0)
        self.assertEqual(self.client.post(self.issue_url, json={"doctor_user_id": self.users["doctor"].id}, headers=self.headers["admin"]).status_code, 400)
        self.assertEqual(self.client.post(self.issue_url, data='{"doctor_user_id":1,"consent_reference":"a","consent_reference":"b"}', content_type="application/json", headers=self.headers["admin"]).status_code, 400)

    def test_reissue_preserves_history_and_requires_new_consent_reference(self):
        first = self.grant().get_json()["grant"]
        self.assertEqual(self.grant(reference="new-reference").status_code, 409)
        self.revoke(first["id"])
        self.assertEqual(self.grant().status_code, 409)
        second = self.grant(reference="new-reference")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(db.session.query(PatientDoctorGrant).count(), 2)
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 200)
        self.revoke(first["id"])
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 200)
        self.revoke(second.get_json()["grant"]["id"])
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 403)

    def test_expired_grant_can_be_reissued_without_rewriting_history(self):
        old = utc_now() - timedelta(days=31)
        with patch("backend.app.api.access_grants.utc_now", return_value=old):
            first = self.grant().get_json()["grant"]
        second = self.grant(reference="renewal-consent")
        self.assertEqual(second.status_code, 201)
        rows = self.client.get(self.issue_url, headers=self.headers["owner"]).get_json()["grants"]
        self.assertEqual([row["status"] for row in rows], ["expired", "issued"])
        self.assertEqual(rows[0]["issued_at"], first["issued_at"])

    def test_grant_metadata_is_owner_scoped_and_nonclinical(self):
        self.grant()
        for actor, status in (("owner", 200), ("admin", 200), ("other", 404), ("doctor", 403)):
            response = self.client.get(self.issue_url, headers=self.headers[actor])
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        for query in ("?after_id=-1", "?after_id=1&after_id=2", "?scope=all"):
            self.assertEqual(self.client.get(self.issue_url + query, headers=self.headers["owner"]).status_code, 400)

    def test_nested_assessment_and_other_doctor_are_denied(self):
        self.grant()
        other = self.client.post(self.other_url, json=valid_payload(), headers=self.headers["other"]).get_json()["assessment"]
        self.assertEqual(self.client.get(self.url + f"/{other['id']}", headers=self.headers["doctor"]).status_code, 404)
        another = User(email="second-doctor@example.invalid", role_id=2, password_hash=self.password_hash)
        db.session.add(another)
        db.session.commit()
        headers = {"Authorization": "Bearer " + issue_token(another)}
        self.assertEqual(self.client.get(self.url, headers=headers).status_code, 403)

    def test_invalid_persisted_grant_fails_closed_and_history_edits_blocked(self):
        grant = self.grant().get_json()["grant"]
        row = db.session.get(PatientDoctorGrant, grant["id"])
        row.consent_reference = "overwrite"
        with self.assertRaises(ValueError):
            db.session.commit()
        db.session.rollback()
        with self.assertRaises(ValueError):
            db.session.execute(update(PatientDoctorGrant).values(scope="review"))
        db.session.rollback()
        # Deliberately tamper via test-only Core SQL: app authorization rejects
        # an expiry that isn't exactly 30 days even if the DB ordering is valid.
        with db.engine.begin() as connection:
            connection.execute(update(PatientDoctorGrant.__table__).where(PatientDoctorGrant.id == grant["id"]).values(expires_at=utc_now() + timedelta(days=60)))
        self.assertEqual(self.client.get(self.url, headers=self.headers["doctor"]).status_code, 403)

    def test_receptionist_and_untrusted_claims_do_not_authorize(self):
        user = User(email="receptionist@example.invalid", role_id=4, password_hash=self.password_hash)
        db.session.add(user)
        db.session.commit()
        reception_headers = {"Authorization": "Bearer " + issue_token(user)}
        self.assertEqual(self.client.get(self.url, headers=reception_headers).status_code, 403)
        self.assertEqual(self.client.get(self.issue_url, headers=reception_headers).status_code, 403)
        self.assertEqual(self.client.post(self.issue_url, json={}, headers=reception_headers).status_code, 403)
        import jwt
        token = issue_token(self.users["admin"])
        claims = jwt.decode(token, self.app.config["JWT_SECRET_KEY"], algorithms=["HS256"], audience="ayur-sage-api", issuer="ayur-sage")
        claims["role"] = "receptionist"
        headers = {"Authorization": "Bearer " + jwt.encode(claims, self.app.config["JWT_SECRET_KEY"], algorithm="HS256")}
        self.assertEqual(self.client.get(self.url, headers=headers).status_code, 403)

    def test_cli_only_authorizes_existing_admin_and_is_idempotent(self):
        runner = self.app.test_cli_runner()
        self.assertNotEqual(runner.invoke(args=["authorize-grant-administrator", "--email", self.users["doctor"].email]).exit_code, 0)
        for _ in range(2):
            self.assertEqual(runner.invoke(args=["authorize-grant-administrator", "--email", self.users["admin"].email]).exit_code, 0)
        self.assertEqual(db.session.query(GrantAdministrator).count(), 1)

    def test_authentication_required_on_grant_operations(self):
        for method, url, payload in (("POST", self.issue_url, {}), ("GET", self.issue_url, None),
            ("POST", self.issue_url + "/1/revoke", {})):
            self.assertEqual(self.client.open(url, method=method, json=payload).status_code, 401)

    def test_real_http_login_grant_read_and_revoke_on_disposable_server(self):
        from werkzeug.serving import make_server, WSGIRequestHandler

        class QuietHandler(WSGIRequestHandler):
            def log(self, *_args, **_kwargs):
                pass

        server = make_server("127.0.0.1", 0, self.app, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"

        def request(path, method="GET", payload=None, token=None):
            headers = {"Accept": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            if payload is not None:
                headers["Content-Type"] = "application/json"
            req = Request(origin + path, method=method, headers=headers,
                          data=json.dumps(payload).encode() if payload is not None else None)
            try:
                response = urlopen(req, timeout=5)
            except HTTPError as error:
                response = error
            with response:
                return response.status, json.loads(response.read())

        try:
            tokens = {}
            for actor in ("owner", "doctor", "admin"):
                status, data = request("/api/auth/login", "POST", {
                    "email": self.users[actor].email, "password": "isolated-fixture-password"})
                self.assertEqual(status, 200)
                tokens[actor] = data["access_token"]
            self.assertEqual(request(self.url, token=tokens["doctor"])[0], 403)
            status, data = request(self.url, "POST", valid_payload(), tokens["owner"])
            self.assertEqual(status, 201)
            assessment_id = data["assessment"]["id"]
            status, data = request(self.issue_url, "POST", {
                "doctor_user_id": self.users["doctor"].id, "consent_reference": "synthetic-http-consent-001"}, tokens["admin"])
            self.assertEqual(status, 201)
            grant_id = data["grant"]["id"]
            self.assertEqual(request(self.url, token=tokens["doctor"])[0], 200)
            self.assertEqual(request(self.url + f"/{assessment_id}", token=tokens["doctor"])[0], 200)
            self.assertEqual(request(self.url, token=tokens["admin"])[0], 403)
            self.assertEqual(request(self.issue_url + f"/{grant_id}/revoke", "POST", {}, tokens["owner"])[0], 200)
            self.assertEqual(request(self.url, token=tokens["doctor"])[0], 403)
            self.assertEqual(request(self.url + f"/{assessment_id}", token=tokens["doctor"])[0], 403)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_migration_matches_models_preserves_assessments_and_mysql_sql(self):
        self.assessment()
        with db.engine.begin() as connection:
            self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
            command.downgrade(migration_config(connection), "0004_assessment_reviews")
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM clinical_assessments").scalar(), 1)
            command.upgrade(migration_config(connection), "head")
        output = io.StringIO()
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+pymysql://localhost/isolated"}):
            command.upgrade(migration_config(output=output), "head", sql=True)
        self.assertIn("CREATE TABLE patient_doctor_grants", output.getvalue())
        self.assertIn("uq_grant_active_pair", output.getvalue())
        self.assertEqual(db.session.query(PatientDoctorGrant).count(), 0)
