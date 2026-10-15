"""Regression for health-only local startup being mistaken for auth readiness."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backend.app import create_app


class LocalAuthStartupTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def local_app(self):
        from backend.local import prepare_local_app
        app = prepare_local_app(self.directory)
        from backend.app.database import db
        with app.app_context():
            engine = db.engine
        self.addCleanup(engine.dispose)
        return app

    def test_missing_environment_local_launcher_fixes_actual_503_and_preserves_standard_startup(self):
        unconfigured = create_app({'TESTING': True}).test_client()
        body = {'email': 'local-test@example.invalid', 'password': 'isolated-test-password-123'}
        self.assertEqual(unconfigured.get('/api/health').status_code, 200)
        for url in ['/api/auth/register', '/api/auth/login']:
            self.assertEqual(unconfigured.post(url, json=body).status_code, 503)
        self.assertEqual(unconfigured.get('/api/auth/me').status_code, 503)

        app = self.local_app()
        self.assertFalse(app.debug)
        client = app.test_client()
        self.assertEqual(client.get('/api/auth/me').status_code, 401)
        self.assertEqual(client.post('/api/auth/register', json=body).status_code, 201)
        login = client.post('/api/auth/login', json=body)
        self.assertEqual(login.status_code, 200)
        data = login.get_json()
        self.assertEqual(data['token_type'], 'Bearer')
        self.assertEqual(data['expires_in'], 900)
        header = {'Authorization': 'Bearer ' + data['access_token']}
        self.assertEqual(client.get('/api/auth/me', headers=header).status_code, 200)
        self.assertEqual(client.post('/api/auth/login', json={**body, 'password': 'wrong'}).status_code, 401)
        self.assertEqual(client.post('/api/auth/register', json=body).status_code, 409)
        self.assertEqual(create_app({'TESTING': True}).test_client().get('/api/auth/me').status_code, 503)
        self.assertNotIn('DATABASE_URL', os.environ)
        self.assertNotIn('JWT_SECRET_KEY', os.environ)

    def test_restart_reuses_local_database_and_secret_for_existing_account_and_token(self):
        body = {'email': 'existing-test@example.invalid', 'password': 'isolated-test-password-123'}
        first = self.local_app()
        client = first.test_client()
        self.assertEqual(client.post('/api/auth/register', json=body).status_code, 201)
        token = client.post('/api/auth/login', json=body).get_json()['access_token']
        restarted = self.local_app()
        self.assertEqual(first.config['JWT_SECRET_KEY'], restarted.config['JWT_SECRET_KEY'])
        self.assertEqual(first.config['SQLALCHEMY_DATABASE_URI'], restarted.config['SQLALCHEMY_DATABASE_URI'])
        existing = restarted.test_client()
        self.assertEqual(existing.post('/api/auth/login', json=body).status_code, 200)
        self.assertEqual(existing.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 200)

    def test_launcher_uses_explicit_directory_and_does_not_adopt_external_database_or_secret(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///not-an-absolute-path', 'JWT_SECRET_KEY': 'private-invalid-value', 'FLASK_DEBUG': 'true'}):
            app = self.local_app()
        self.assertEqual(Path(app.config['SQLALCHEMY_DATABASE_URI'].database).parent, self.directory)
        self.assertNotEqual(app.config['JWT_SECRET_KEY'], 'private-invalid-value')
        self.assertFalse(app.debug)

    def test_local_port_argument_is_strict_and_server_stays_on_loopback(self):
        from backend.local import main
        app = self.local_app()
        with patch('backend.local.prepare_local_app', return_value=app), patch.object(app, 'run') as run:
            main(['--data-dir', str(self.directory), '--port', '5101'])
        run.assert_called_once_with(host='127.0.0.1', port=5101, debug=False, use_reloader=False)
        for port in ['0', '65536', 'invalid']:
            with self.subTest(port=port), patch('sys.stderr'), self.assertRaises(SystemExit):
                main(['--port', port])
