"""Disposable loopback auth fixture; no persistent DB, real accounts or secrets."""
import os
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'backend'))
from alembic import command
from werkzeug.serving import make_server, WSGIRequestHandler
from backend.app import create_app
from backend.app.database import db
from backend.app.auth.routes import create_account
from test_database import migration_config

# Explicit isolated config, independent of any operator environment.
for name in ('DATABASE_URL', 'JWT_SECRET_KEY', 'SECRET_KEY', 'JWT_ACCESS_TOKEN_SECONDS', 'FLASK_DEBUG'):
    os.environ.pop(name, None)
database = 'sqlite:///:memory:'
mysql_identity = None
if '--mysql' in sys.argv:
    import traceback
    def safe_mysql_failure(kind, error, trace):
        original = getattr(error, 'orig', error)
        code = original.args[0] if original.args and isinstance(original.args[0], int) else 'no-code'
        frame = traceback.extract_tb(trace)[-1]
        print(f'MYSQL_APP_FAILED {kind.__name__} {code} {frame.name}:{frame.lineno}', file=sys.stderr, flush=True)
    sys.excepthook = safe_mysql_failure
    from sqlalchemy.engine import make_url
    from sqlalchemy import text
    database = os.environ.pop('AYURSAGE_E2E_MYSQL_URL')
    identity_file = Path(os.environ.pop('AYURSAGE_E2E_MYSQL_IDENTITY')).resolve()
    expected_root = (ROOT / '.local').resolve()
    assert identity_file.parent.parent == expected_root and identity_file.parent.name.startswith('mysql-e2e-')
    mysql_identity = json.loads(identity_file.read_text(encoding='utf-8'))
    url = make_url(database)
    assert url.drivername == 'mysql+pymysql' and url.host == '127.0.0.1'
    assert url.database == mysql_identity['schema'] and url.database.startswith('ayursage_e2e_')
    assert url.username == mysql_identity['username'] and url.port == mysql_identity['port']
app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': database, 'JWT_SECRET_KEY': secrets.token_urlsafe(48)})
with app.app_context():
    if mysql_identity:
        with db.engine.connect() as connection:
            observed = connection.execute(text('SELECT DATABASE(), @@datadir, @@port, @@server_uuid')).one()
            assert observed[0] == mysql_identity['schema'] and observed[2] == mysql_identity['port']
            assert Path(observed[1]).resolve() == Path(mysql_identity['datadir']).resolve()
            assert observed[3] == mysql_identity['server_uuid'] and db.engine.dialect.name == 'mysql'
            assert connection.execute(text('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()')).scalar_one() == 0
    with db.engine.begin() as connection:
        command.upgrade(migration_config(connection), 'head')
    from sqlalchemy import text
    with db.engine.connect() as connection:
        head = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    print('DATABASE ' + json.dumps({'dialect': db.engine.dialect.name, 'migration': head,
        'schema': mysql_identity['schema'] if mysql_identity else None}), flush=True)
    for role in ('doctor', 'admin', 'receptionist'):
        create_account(role + '@example.invalid', 'fixture-password-123', role)

if '--doctor-access-fixtures' in sys.argv:
    # Opt-in browser/HTTP fixture only. No grant bypass or test-only API routes.
    from unittest.mock import patch
    from backend.app.services.v17 import V17Service
    assert app.config['V17_MODEL_LOADING_ENABLED'] is False
    for method in ('load', 'predict'):
        patch.object(V17Service, method, side_effect=AssertionError('ML execution forbidden in access tests')).start()
    with app.app_context():
        create_account('other-doctor@example.invalid', 'fixture-password-123', 'doctor')
    result = app.test_cli_runner().invoke(args=['authorize-grant-administrator', '--email', 'admin@example.invalid'])
    assert result.exit_code == 0, 'Synthetic grant-administrator provisioning failed'
    if mysql_identity:
        sys.path.insert(0, str(Path(__file__).parent / 'e2e'))
        from mysql_assertions import verify_mysql
        print('MYSQL_CHECKS ' + json.dumps(verify_mysql(app)), flush=True)

if '--patient-fixtures' in sys.argv:
    import ast
    import json
    from backend.app.models import User, ClinicalAssessment
    from backend.app.auth.security import hash_password
    from backend.app.api.assessment_validation import CATEGORICAL_INPUTS, NUMERIC_INPUTS
    with app.app_context():
        db.session.add(User(email='legacy-patient@example.invalid', role_id=1,
                            password_hash=hash_password('fixture-password-123')))
        owner = create_account('record-owner@example.invalid', 'fixture-password-123', 'patient')
        db.session.add(ClinicalAssessment(patient_id=owner.patient.id,
                                        recorded_by_user_id=owner.id, inputs=None, notes='legacy fixture'))
        db.session.commit()
    # Parse frozen declarations without executing training code or loading artifacts.
    source = ast.parse((ROOT / 'ml/source/AyurSage_Training_v17.py').read_text(encoding='utf-8'))
    constants = {}
    for node in source.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {'CATEGORICAL_COLS', 'NUMERIC_COLS'}:
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    assert list(CATEGORICAL_INPUTS) == constants['CATEGORICAL_COLS']
    assert list(NUMERIC_INPUTS) == constants['NUMERIC_COLS']
    print('CONTRACT ' + json.dumps(constants), flush=True)

class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass

server = make_server('127.0.0.1', 0, app, request_handler=QuietHandler)
print('READY ' + str(server.server_port), flush=True)
server.serve_forever()
