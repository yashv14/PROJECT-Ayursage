# Authentication, JWT and RBAC - 13 October 2026 (Asia/Calcutta)

This milestone reuses the Flask factory, blueprint, SQLAlchemy extension and
existing models. No patient-management APIs, prediction, reports, frontend,
second backend or deployment was added. Watchdog Step 1.3 remains deferred and
NOT ACCEPTED; V17 loading remains disabled.

## Inspection and configuration

Inspected the factory, configuration, user/role models, database initialization,
Alembic environment and initial migration, dependencies, existing 31 backend tests
and database-foundation.md. Installed-package inspection found Werkzeug 3.1.9
password hashing but no JWT library. Reused Werkzeug scrypt and added only PyJWT
2.15.1, installed in project-local `.venv` and pinned in both requirement files.

Uses the official [Werkzeug hashing API](https://werkzeug.palletsprojects.com/en/stable/utils/#module-werkzeug.security)
and [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html).

`DATABASE_URL` retains its existing behavior. `JWT_SECRET_KEY` is independent from
Flask SECRET_KEY, with no default/fallback. Supply a cryptographically generated
random secret of at least 32 bytes through environment injection; never commit it.
Startup checks minimum byte length and basic character diversity, which cannot
prove entropy. No automatic `.env` loading was added.
`JWT_ACCESS_TOKEN_SECONDS` defaults to 900; accepts integers 60-86400. Invalid
settings fail without echoing secrets. Missing JWT secret or database configuration
makes authentication requests return 503 while health remains available. Startup
does not connect or auto-migrate. An unavailable/unmigrated database fails with
generic 503 auth responses; database driver errors are not logged.

## Endpoints and security behavior

| Endpoint | Success | Errors |
| --- | --- | --- |
| POST /api/auth/register | JSON email/password only; 201 user id/email/role | 400 invalid input, 409 duplicate, 503 unavailable |
| POST /api/auth/login | JSON email/password only; 200 access_token/token_type/expires_in | 400 invalid input, 401 wrong credentials, 503 unavailable |
| GET /api/auth/me | Bearer header; 200 user id/email/current role | 401 missing/invalid token, 503 unavailable |
| GET /api/health | 200 status ok; liveness only | Existing HTTP error behavior |

Credential bodies are capped at 4096 bytes (413 if exceeded). Emails are ASCII,
trimmed/lowercased, bounded to 254 characters (64-character local part), with basic
syntax validation; address delivery/ownership is not verified. Registration
passwords are 12-128 characters, nonblank and without NUL; login accepts bounded
nonblank passwords so shorter incorrect attempts also receive generic 401.
Unknown users and wrong credentials produce identical responses; a dummy scrypt
verification reduces the obvious unknown-account timing difference.

Only independently salted `scrypt:32768:8:1` hashes are stored. Public registration
rejects every extra field, including role/role_id/password_hash. Patient user/profile
creation is atomic; duplicate races roll back. Successful auth responses use
Cache-Control: no-store. Errors use the existing JSON format; 401 supplies
WWW-Authenticate: Bearer. Auth code does not log passwords, tokens or patient data.

HS256 is fixed server-side. Tokens contain subject id, iat, nbf, exp, issuer,
audience, jti and access token type; no email, role, password or patient data.
Verification requires those claims, valid signature, expected issuer/audience,
validity window and numeric subject. Only bounded bearer headers authenticate,
never cookies or query parameters. Protected requests resolve the current user and
role from the database; deleted/passwordless users cannot authenticate. Roles in
untrusted token payloads do not grant permissions.

## Reusable authorization and privileged provisioning

`auth_required` sets flask.g.current_user after verification.
`roles_required('doctor', 'admin')`, for example, authenticates and permits only
its explicit role set; there is no automatic administrator override. Existing
administrator code is `admin`. Unknown decorator role codes fail configuration.
Permission-test routes are registered only in tests, not the application.

`require_patient_owner(patient)` is intended inside authenticated future patient
views. It permits only patient-role users whose id matches owner_user_id. Nonowners,
doctors and administrators are denied. No doctor access-grant policy was invented;
future APIs must implement the approved doctor/admin scope and apply ownership
checks to actual patient resources.

An operator with trusted local process/database access can provision a new doctor
or administrator through Flask CLI, after configuration and migrations:

```powershell
.venv/Scripts/python.exe -B -m flask --app backend.app create-privileged-user --email <operator-selected-email> --role doctor
```

Use `--role admin` for administrators. A hidden password prompt requires
confirmation; passwords are never CLI options or printed. No default privileged
account exists. The command creates new accounts only and refuses existing-email
elevation. Invalid input, duplicates and DB failures exit unsuccessfully with
generic errors. Tests used disposable local accounts; no real account was created.

## Migration implications

Revision `0002_password_hash` adds nullable VARCHAR(512) password_hash to users.
Revision 0001 is unchanged. Null preserves legacy rows/relations but disables login
for those accounts; no default credentials or backfill are invented. Legacy
mixed-case emails are checked case-insensitively; ambiguous duplicates cannot log
in. New addresses are canonical lowercase.

After setting DATABASE_URL to the intended database, upgrade using:

```powershell
.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini upgrade head
```

This is a usage instruction, not a performed production/CLI migration. Startup
never migrates. Downgrade to revision 0001 removes hashes. Tests performed upgrade,
downgrade and reupgrade with legacy rows in isolated SQLite and confirmed model
metadata agrees with the schema. Offline MySQL SQL for the added column was
generated and checked, not applied to live MySQL.

## Executed checks

Exact commands from the workspace root:

```powershell
.venv/Scripts/python.exe -B -m pip list
.venv/Scripts/python.exe -m pip install 'PyJWT>=2.10,<3'
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

Install succeeded with approved access, adding PyJWT 2.15.1 only. Full suite ran
with approved temporary-file access required by the existing file-database test.
First run: 52 tests, one new fixture error caused by retained authenticated state
in its shared application context. The fixture was corrected; authentication also
clears previous current-user state before checking credentials. Final full run:
**52 tests, 4.685 seconds, OK, exit 0**. All original health/database coverage remains.
The old health-only route assertion now checks all four milestone routes; the
MySQL offline test also asserts the new password-hash ADD COLUMN.

Coverage: registration/login/me, hash verification and salts, invalid credentials,
duplicates, input validation and privilege injection, missing/malformed/expired/
future/wrong-signature/unsigned JWTs, claims/issuer/audience, all three role
permission combinations, DB role changes, ownership denial, null/deleted users,
CLI success/failure, failed-write rollback and legacy-row migration preservation.

pip check: exit 0, `No broken requirements found`. Routes: exit 0:

```text
api.auth.login     POST  /api/auth/login
api.auth.me        GET   /api/auth/me
api.auth.register  POST  /api/auth/register
api.health         GET   /api/health
```

The final run also rejects overflowing JWT timestamps and confirms database
failures never call the application error logger.

Additional executed commands:

```powershell
.venv/Scripts/python.exe -B -c "import importlib.metadata as m,pathlib; entries=pathlib.Path('backend/requirements.txt').read_text().splitlines(); assert all(m.version(line.split('==')[0])==line.split('==')[1] for line in entries if line and not line.startswith('#')); print('All pinned runtime versions match installed distributions')"
.venv/Scripts/python.exe -B -c "import hashlib,json,pathlib; roots=['ml','infra','tests/integration','tests/ml','frontend']; print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in roots for p in pathlib.Path(root).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','.venv','__pycache__','.npm-cache'))}))"
```

Pin check exited 0: all pinned runtime versions match installed distributions.
SHA-256 inventories captured before and after editing were compared: **18 files,
zero changes, zero additions/removals in those inventoried roots**. Includes V17
model, training source, dataset, inference controls, infrastructure/watchdog code,
ML/integration tests and frontend manifests. Environments, bytecode and caches
were excluded. No protected production artifact, loading control, watchdog file,
Docker resource or unrelated workflow was edited. Initial migration 0001 was
retained; the password-hash change is a new revision only.

## Changed files

Updated: backend/app/__init__.py, backend/app/api/__init__.py,
backend/app/errors.py, backend/app/models/__init__.py, backend/config/__init__.py,
backend/requirements.in, backend/requirements.txt, tests/backend/test_foundation.py,
tests/backend/test_database.py, .env.example, README.md,
docs/architecture/overview.md, docs/setup/implementation-checklist.md,
docs/setup/database-foundation.md (historical-record link only).

Added: backend/app/auth/__init__.py, backend/app/auth/security.py,
backend/app/auth/routes.py, backend/migrations/versions/0002_password_hash.py,
tests/backend/test_auth.py, docs/setup/authentication.md.
Ignored project-local `.venv` received PyJWT. There is no Git repository, so no
tracked-file status, Git diff or commit is claimed.

## Unperformed checks and stopping point

No live MySQL connection/schema/constraint/collation verification, production or
cloud migrations, real account provisioning, live HTTP server, Docker, deployment,
clean-environment install, frontend, V17 loading/inference or watchdog tests were
performed. No production credentials were requested or used.

This is a tested authentication foundation, not production deployment acceptance.
Refresh tokens, logout/revocation, password reset, email verification, distributed
login throttling, transport/proxy configuration and patient/doctor APIs are not
implemented. Tokens remain valid until expiry unless the user is removed or made
passwordless; current role changes affect authorization on the next request.
Work stops after this milestone.
