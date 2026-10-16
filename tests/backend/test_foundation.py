"""Phase 2 tests; require no database, secrets, V17 artifacts or cloud service."""

import os
import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.__main__ import main


class FoundationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_missing_route_is_json(self):
        response = self.client.get("/api/missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": {"code": 404, "message": "Not Found"}})

    def test_method_not_allowed_preserves_allow_header(self):
        response = self.client.post("/api/health")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["error"]["code"], 405)
        self.assertIn("GET", response.headers["Allow"])

    def test_unhandled_error_does_not_expose_details(self):
        app = create_app({"TESTING": False, "DEBUG": False})

        @app.get("/api/test-error")
        def fail():
            raise RuntimeError("private-test-detail")

        with self.assertLogs(app.logger, level="ERROR"):
            response = app.test_client().get("/api/test-error")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": {"code": 500, "message": "Internal Server Error"}})
        self.assertNotIn("private-test-detail", response.get_data(as_text=True))

    def test_safe_defaults(self):
        self.assertFalse(self.app.debug)
        self.assertIsNone(self.app.secret_key)
        self.assertEqual(self.app.config["BACKEND_PORT"], 5000)

    def test_environment_values_are_loaded(self):
        with patch.dict(os.environ, {"SECRET_KEY": "test-only-value", "BACKEND_PORT": "5100", "FLASK_DEBUG": "true"}):
            app = create_app()
        self.assertEqual(app.secret_key, "test-only-value")
        self.assertEqual(app.config["BACKEND_PORT"], 5100)
        self.assertTrue(app.debug)
        self.assertNotIn("test-only-value", app.test_client().get("/api/health").get_data(as_text=True))

    def test_blank_environment_uses_defaults(self):
        with patch.dict(os.environ, {"SECRET_KEY": "", "BACKEND_PORT": "", "FLASK_DEBUG": ""}):
            app = create_app()
        self.assertIsNone(app.secret_key)
        self.assertEqual(app.config["BACKEND_PORT"], 5000)
        self.assertFalse(app.debug)

    def test_invalid_ports_are_rejected_without_echoing_values(self):
        for value in ("0", "65536", "-1", "private-invalid-value"):
            with self.subTest(value=value), patch.dict(os.environ, {"BACKEND_PORT": value}):
                with self.assertRaises(ValueError) as caught:
                    create_app()
                self.assertEqual(str(caught.exception), "BACKEND_PORT must be an integer between 1 and 65535")

    def test_invalid_debug_is_rejected(self):
        with patch.dict(os.environ, {"FLASK_DEBUG": "invalid"}):
            with self.assertRaisesRegex(ValueError, "FLASK_DEBUG must be"):
                create_app()

    def test_supported_debug_values(self):
        for value, expected in (("0", False), ("false", False), ("1", True), ("TRUE", True)):
            with self.subTest(value=value), patch.dict(os.environ, {"FLASK_DEBUG": value}):
                self.assertEqual(create_app().debug, expected)

    def test_factories_do_not_share_configuration(self):
        first = create_app({"SECRET_KEY": "test-only-first"})
        second = create_app()
        self.assertEqual(first.secret_key, "test-only-first")
        self.assertIsNone(second.secret_key)

    def test_only_milestone_routes_registered(self):
        self.assertEqual(sorted(rule.rule for rule in self.app.url_map.iter_rules()),
                         ["/api/auth/login", "/api/auth/me", "/api/auth/register", "/api/health",
                          "/api/patients", "/api/patients/<int:patient_id>",
                          "/api/patients/<int:patient_id>/assessments",
                          "/api/patients/<int:patient_id>/assessments",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>/report",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>/report",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>/report/content",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>/report/download-link",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>/reviews",
                          "/api/patients/<int:patient_id>/assessments/<int:assessment_id>/reviews",
                          "/api/patients/<int:patient_id>/doctor-access-grants",
                          "/api/patients/<int:patient_id>/doctor-access-grants",
                          "/api/patients/<int:patient_id>/doctor-access-grants/<int:grant_id>/revoke",
                          "/api/patients/authorized", "/api/patients/me",
                          "/api/reception/appointments", "/api/reception/appointments",
                          "/api/reception/appointments/<int:appointment_id>/reschedule",
                          "/api/reception/appointments/<int:appointment_id>/status",
                          "/api/reception/doctors", "/api/reception/patients"])

    def test_entry_point_uses_environment_port(self):
        with patch.dict(os.environ, {"BACKEND_PORT": "5101"}), patch("flask.Flask.run") as run:
            main()
        run.assert_called_once_with(host="127.0.0.1", port=5101)


if __name__ == "__main__":
    unittest.main()
