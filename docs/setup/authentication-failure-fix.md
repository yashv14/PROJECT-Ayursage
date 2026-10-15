# Authentication failure diagnosis and local correction — 13 October 2026

## Exact root cause and first failing boundary

The Flask process serving 127.0.0.1:5000 had **neither DATABASE_URL nor
JWT_SECRET_KEY in its process environment**. Presence-only inspection of the
verified AYUR-SAGE backend process confirmed both absent; no values were printed
or saved. There were no populated local .env files, and the standard backend
intentionally reads the process environment without automatically loading .env.

The database extension was therefore disabled and the JWT signing secret was
unset. auth/security.py's require_auth_configuration rejects this state with 503
before request credential validation, database/password verification or JWT work.
The health route intentionally remains available and is not auth readiness.

Before editing, live HTTP probes reproduced:

| Request | Through localhost:5174 | Direct Flask :5000 |
| --- | --- | --- |
| GET /api/health | 200 JSON | 200 JSON |
| GET /api/auth/me without token | 503 JSON Service Unavailable | Same 503 |

These results prove the frontend port/proxy reached Flask; the first failed
boundary was **Flask authentication configuration**, not the form, API path,
proxy, password hash, JWT validation or client state. The user's reported message
was "The authentication service is unavailable. Please try again later.", which
is the existing API client's correct mapping of this 503.
The existing missing-configuration backend test reproduces the same registration,
login and /me rejection. All baseline tests passed because fixtures supplied
JWT configuration and isolated migrated databases; they did not imply the user's
running backend was configured.

## Inspected contracts and startup behavior

Read authentication.md, frontend-foundation.md, the current auth context/session,
AuthPage, validation, auth/API services, routing, Vite config, backend factory,
entry point, configuration, auth routes/security/init, database init, API blueprint,
error handlers, existing auth and startup tests, and Alembic setup.

| Endpoint | Request | Success |
| --- | --- | --- |
| POST /api/auth/register | JSON exactly email/password | 201 `{user: {id, email, role}}`; public patient registration; no token |
| POST /api/auth/login | JSON exactly email/password | 200 `{access_token, token_type: "Bearer", expires_in: 900}` with default lifetime |
| GET /api/auth/me | Authorization: Bearer access token | 200 `{user: {id, email, role}}` |

Registration/login validation, scrypt password hashing, HS256 issuance and required
claim/signature/issuer/audience checks agree with frontend expectations. Generic
errors retain `{error: {code, message}}`; 401 includes WWW-Authenticate: Bearer.
The frontend performs /me before establishing authenticated state and never decodes
roles from the token. The existing in-memory logout/expiry behavior is unchanged.

The running Vite process on 5174 belongs to frontend/node_modules/vite in this
workspace and was started with a 5174 argument. Default vite.config.js is unchanged:
relative /api is proxied to 127.0.0.1:5000, changeOrigin true. The live probes verify
this behavior for localhost as well as 127.0.0.1. There is no evidence of a URL or
CORS failure, and no proxy/frontend change was made. Vite's default 5173 setting
was not altered; keep the explicit --port 5174 argument for this debugging session.

## Small targeted correction

Added **backend/local.py**, an explicitly invoked local-development launcher:

```powershell
# From C:\Users\yvasa\Videos\PROJECT-Ayursage
.venv/Scripts/python.exe -B -m backend.local --port 5000
```

It uses the existing Flask factory, models, auth implementation and Alembic
migrations. It prepares a dedicated local SQLite database at
`.local/auth/auth.sqlite3`, creates a cryptographically random persistent signing
key at `.local/auth/jwt.key`, and applies existing migrations to that selected
local database. No existing database was configured in the failing process and
no existing database/schema was modified. There are no new/default users,
passwords, routes or schema definitions in this launcher.

The launcher is loopback-only, debug/reloader disabled, and retains the 900-second
JWT lifetime. It deliberately uses its own local configuration rather than an
inherited external database. --data-dir can select another explicit local directory;
--port accepts only 1–65535. Local database and key are reused across restarts, so
existing local accounts and valid tokens continue to work.

This does not change the standard factory/entry point's environment-only,
no-default-secret, no-auto-migration behavior. `python -m backend` still requires
explicit JWT_SECRET_KEY/DATABASE_URL and operator-run migrations for the intended
database. The opt-in launcher is the correction for this local debugging workflow,
not a production/MySQL configuration change or acceptance claim.

Verified process ownership before stopping the previous Flask listener: its parent
was this workspace's .venv/Scripts/python.exe. Restarted only that backend using
Start-Process with WindowStyle Hidden. The original frontend process remained
unchanged: PID 3096, listening at 127.0.0.1:5174 before and after. The repaired
backend listens at 127.0.0.1:5000 (listener PID 22460 at verification); launcher PID
36612. Both are left running for this debugging session.

Ignored runtime files: .local/auth/auth.sqlite3, jwt.key, backend.stdout.log,
backend.stderr.log and backend.pid.log. Existing ignore patterns cover *.sqlite*,
*.key and *.log; .gitignore was not edited. The generated test account remains
only in this local database and has no clinical assessments; its generated
credentials were not printed or saved as a credential fixture.

## Reproduction and verification steps

1. Start the standard factory/backend without DATABASE_URL and JWT_SECRET_KEY.
   Its health response is 200, but auth registration/login/me are 503. This is
   reproduced in the regression test with a cleared environment; the original
   running server also returned this exact health/me result.
2. Invoke the explicit local launcher above, with port 5000 available for this
   workspace's backend. It configures auth and migrates its dedicated local DB.
3. Keep the existing frontend at http://localhost:5174. If restarting it later:

   ```powershell
   cd frontend
   npm run dev -- --port 5174
   ```

4. An unauthenticated GET http://localhost:5174/api/auth/me now returns 401,
   rather than configuration failure 503. Health remains 200.
5. Register a generated test account through the live proxy, then sign in and
   verify bearer /me. Clear the in-memory session, verify anonymous protected-route
   redirection, try a wrong password (401), and sign in again with the now-existing
   test account.

Step 5 was actually executed with Node using the **existing** createApiClient,
createAuthService, createSession and resolveRoute modules and base URL
http://localhost:5174/api. Generated email/password/token values stayed in memory;
output included only PASS descriptions, with error details suppressed. Results:

- Live registration passed; registration alone did not establish auth state.
- Live login and bearer /me passed; returned identity matched the registered account.
- Auth state/route resolver passed: login redirects to patient home; patient route
  opens; doctor route is forbidden for the test patient.
- Logout cleared token/identity; protected patient route resolves to login; an
  authenticated client request without a token fails 401.
- Wrong credentials returned real Flask 401 without establishing auth state.
- A second login after logout with the existing test account passed, including /me.

These are live HTTP/client-state/resolver checks, **not a mounted browser flow**.
The browser inventory was empty, so browser clicks, visual rendering and actual
hash-navigation/focus were not tested. No live browser-flow success is claimed.

## Regression tests and exact commands

Before the correction, existing suites passed: **36 frontend tests** (5.252 s),
**93 backend tests** (16.103 s). Added tests before the launcher implementation;
the focused run failed with four ModuleNotFoundError errors for the not-yet-added
backend.local module. The 503 reproduction assertions were independently verified
against the live server and the existing missing-configuration test; this import
failure is not described as an auth assertion failure. After implementing the
launcher, all four focused tests passed (1.308 s):

- test_missing_environment_local_launcher_fixes_actual_503_and_preserves_standard_startup
- test_restart_reuses_local_database_and_secret_for_existing_account_and_token
- test_launcher_uses_explicit_directory_and_does_not_adopt_external_database_or_secret
- test_local_port_argument_is_strict_and_server_stays_on_loopback

They use temporary isolated directories, generated signing keys and disposable
SQLite databases with existing migrations. No production credentials or data.
They verify the exact unconfigured 503 state, configured registration/login/me,
invalid credentials, duplicate registration, normal factory behavior, persistent
accounts/key/token after restart and local-only configuration/port semantics.

Executed from the frontend directory:

```powershell
npm test
npm run build
```

Final outcomes: **36 passed, 0 failed/skipped**, 4.474 seconds; production build
exit 0, 35 modules, 314 ms. JS/CSS output content matches the previous milestone
because frontend application source is unchanged.

Executed from the workspace root:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_local_auth.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

Final outcomes: **97 backend tests passed** (93 existing + 4 new), 17.414 seconds;
`No broken requirements found`; same 10 route operations. All exit 0. Normal
process/temp-file access was approved for test/build runs as in prior milestones.

## Exact changed files and preservation

Added:

- backend/local.py — explicit configured local auth/database startup
- tests/backend/test_local_auth.py — four regression tests for the root cause and launcher
- docs/setup/authentication-failure-fix.md — this diagnosis/reproduction/test record

Updated:

- README.md — document the local auth launcher, debugging port and report

Generated only ignored local runtime/key/database/log files and frontend build/cache
output. All **84 pre-existing inventoried files** under backend, frontend/src,
frontend/tests, ml, infra and tests, plus frontend vite.config.js/package manifests,
were SHA-256 identical after the correction. Inventory additions were only
backend/local.py and tests/backend/test_local_auth.py. The temporary inventory was
removed after comparison. No authentication implementation, patient assessment
functionality, dependency, migration, V17 artifact/training/loading file, watchdog
or Docker resource was changed. No Git status/diff/commit claim: Git is not initialized.

## Remaining limits and stopping point

No mounted live browser flow, live MySQL/previously provisioned user account,
production configuration, Docker/cloud, V17 inference/loading or watchdog acceptance
checks were performed. Existing fixture accounts and the generated live local test
account were checked; no real user's credentials were requested or used. Logout is
still local token removal, not server token revocation, as the existing API contract
has no logout/revocation endpoint. The local HTTP authentication path is fixed and
verified; feature development has not resumed.
