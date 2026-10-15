# Authentication runtime recurrence — 13 October 2026

This records fresh evidence from the running application, after the earlier
`authentication-failure-fix.md` report. The defect recurred because port 5000 was
again serving the standard, unconfigured Flask factory. The existing local
launcher was present on disk but was not the running backend.

## Reproduction and first failing boundary

The process listening on port 5000 was PID 3324, launched by this workspace's
`.venv/Scripts/python.exe` (parent PID 10096), with command fragments
`-m flask --app backend.app run`. A presence-only inspection of that process's
environment confirmed **both DATABASE_URL and JWT_SECRET_KEY absent**. No values,
credentials, tokens or account data were printed. Vite PID 24044 belonged to this
workspace and remained on port 5174 throughout the repair.

Live HTTP requests before repair, using generated synthetic credentials in memory:

| Exact request | Status | Safe response |
| --- | --- | --- |
| POST http://localhost:5174/api/auth/register | 503 | application/json; `{"error":{"code":503,"message":"Service Unavailable"}}` |
| POST http://localhost:5174/api/auth/login | 503 | Same JSON error |
| GET http://localhost:5174/api/auth/me, no bearer token | 503 | Same JSON error |
| GET http://localhost:5174/api/health | 200 | application/json |

The corresponding four requests directly to `http://127.0.0.1:5000` had the same
statuses. Vite was successfully forwarding `/api`. The served AuthContext module
used the default `/api` base URL; no populated local environment files were found.

`AuthPage.jsx` normalizes email and submits email/password only via the existing
auth service and API client. Confirmation is client-only. Flask's routes are
`POST /api/auth/register`, `POST /api/auth/login` and `GET /api/auth/me`.
The first failing boundary was `require_auth_configuration()` in
`backend/app/auth/security.py`: missing JWT configuration and disabled database
extension cause Werkzeug `ServiceUnavailable` before credential validation,
database write/password verification or JWT processing. This was traced from the
running process configuration and guard ordering, not from an invented traceback.
No database exception was needed to explain the observed failure.

Flask's error handler deliberately serializes generic HTTP errors. The API client
maps HTTP 503 to the exact reported text, “The authentication service is unavailable.
Please try again later.” It was not hiding a more specific validation response;
Flask had returned only `Service Unavailable`.

Read the auth/setup reports, current auth page/context/session/services/routing,
Vite configuration, Flask factory/configuration/database initialization, auth
routes/validation/hash/JWT helpers, error handlers, launcher and relevant tests.
The success contracts still agree: registration returns 201 `{user}`, login 200
`{access_token, token_type: "Bearer", expires_in}`, and bearer-authenticated `/me`
returns 200 `{user}`. Login resolves identity through `/me` before setting session
state. No contract correction was required.

## Targeted repair and regression

Stopped only PID 3324 after rechecking the port, command and workspace parent.
Started the existing launcher, using hidden-window Start-Process and local log
redirection, with these executable arguments from the workspace root:

```powershell
.venv/Scripts/python.exe -B -u -m backend.local --port 5000
```

The replacement listener was PID 26200, launcher parent PID 7048. It reused
`.local/auth/auth.sqlite3` and `.local/auth/jwt.key`. The original Vite PID 24044
was untouched. No new backend, schema, environment secret fallback or auth system
was introduced. Standard factory startup continues to require its own explicit
database/JWT environment configuration.

Added a deliberately opt-in live regression, outside the default isolated suite:
`frontend/tests/live/auth.test.js`, test name **running port 5174: auth readiness,
registration, persisted login, JWT, errors and logout**. It uses the existing API,
auth, session and route modules against the actual port 5174. It prints only safe
method/path/status diagnostics, creates one synthetic patient per successful run,
and creates no assessments. It failed before repair with **503 !== 401** at the
unauthenticated `/me` readiness check, and passed after repair. Health 200 alone
can no longer make this runtime check pass.

Added named VS Code tasks for the existing local backend command on 5000 and Vite
on 5174. They are manual tasks, do not kill processes, and must be started only
when their respective port is free. They prevent ambiguity about the intended
local startup command; they do not change the standard Flask factory.

## Results and exact commands

From `C:\Users\yvasa\Videos\PROJECT-Ayursage\frontend`:

| Command | Result |
| --- | --- |
| `npm test` before repair | 36 passed, 0 failed/skipped |
| `npm run test:auth:live` before repair | 1 failed: actual auth 503, expected 401 |
| `npm run test:auth:live` after repair | 1 passed, 0 failed/skipped |
| `npm test` after repair | 36 passed, 0 failed/skipped; 4.315 seconds |
| `npm run build` | Exit 0; Vite 8.3.4; 35 modules; 388 ms |

From the workspace root:

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v` before repair | 97 passed; 11.415 seconds |
| Same command after repair | 97 passed; 21.601 seconds |
| `.venv/Scripts/python.exe -B -m pip check` | Exit 0; No broken requirements found |

The first sandboxed attempt to launch the new Node test returned `spawn EPERM`.
Repeating with approved subprocess access exposed the actual 503 assertion above.
Final Node/Vite and backend suite runs used that access; no dependency changes
were required.

The live check verified registration 201, duplicate registration 409, login 200,
bearer `/me` 200 matching the new account, wrong password 401 with the safe
“Email or password is incorrect.” message, logout clearing identity/token,
anonymous protected-route redirect and role guards, and a fresh-client login to
the now-existing account. A separate read-only SQLite query confirmed exactly
one additional user and patient, a stored scrypt hash for the synthetic patient,
an unchanged assessment count, and an unchanged signing-key checksum.

Existing regressions also passed, including
`test_missing_configuration_denies_auth_but_preserves_health`,
`test_missing_environment_local_launcher_fixes_actual_503_and_preserves_standard_startup`,
`test_restart_reuses_local_database_and_secret_for_existing_account_and_token`,
the Vite/Flask auth contract test, API error/network handling and session logout
tests. Their configured fixtures explain why they passed while the live runtime
was broken. Unavailable/network error mapping is covered by these tests and the
auth page's existing alert binding was inspected; visible browser alerts were
not exercised.

## Exact changed files and preservation

- Added `.vscode/tasks.json`: explicit local backend and port-5174 frontend tasks.
- Added `frontend/tests/live/auth.test.js`: opt-in running-runtime regression.
- Updated `frontend/package.json`: `test:auth:live` script only.
- Updated `README.md`: restart tasks, readiness check and this evidence report.
- Added `docs/setup/authentication-runtime-repair.md`: this report.

Runtime-only changes: reused local database gained one synthetic patient account;
local backend PID/stdout/stderr logs were refreshed; frontend dist/cache regenerated.
The generated synthetic password was not retained. No real account was queried.
SHA-256 comparison of all 83 inventoried existing files in backend, frontend
source/tests, tests, ml and infra found **zero changed existing files**. In
particular authentication and assessment source, migrations, model/training/loading
controls, watchdog code and Docker resources were preserved. Temporary comparison
files were removed.

## Browser limitation and exact remaining checks

`cua.getState()` returned `apps: []` and `browsers: []`. Registration and login
were verified over live HTTP through Vite, **not in a real browser session**.
Actual clicks, form event dispatch, visible error/success states and navigation
remain unverified. VS Code task invocation through the IDE also was not exercised;
the equivalent backend command was executed and task JSON validated.

To complete browser verification, open `http://localhost:5174/#/register`, open
DevTools Network filtered to `/api/auth`, and create a fresh synthetic account
using a 12–128 character password. Expect POST `/api/auth/register` 201 and the
success link. Follow it to sign in: expect POST `/api/auth/login` 200 then GET
`/api/auth/me` 200 and `#/patient`. Log out, navigate to `#/patient`, and expect
`#/login`; retry with an incorrect password and expect 401 plus the safe error.
For the unavailable UI check, use DevTools request blocking for
`http://localhost:5174/api/auth/*`, submit, and expect a connection error alert;
disable request blocking immediately afterward. Record only method/path/status
and safe error text; do not share request bodies, Authorization headers or tokens.

No live MySQL, production deployment, V17 inference or additional feature work
was undertaken.

## Follow-up: live patient workflow — 13 October 2026 (Asia/Calcutta)

Read the completed four-role system map, authentication reports, frontend foundation,
patient assessment API/UI reports and current implementation. Reused the existing
routes, client, session, patient workspace, local launcher and migrations.

Fresh runtime evidence differs from the earlier 503: `npm run test:auth:live`
initially failed with `ECONNREFUSED` at its first health request to port 5174
(both ::1 and 127.0.0.1). Read-only listener inspection confirmed **no Vite listener**
on 5174, while Flask listener PID 26200 remained on 5000. Its command and parent
PID 7048 identify this workspace's `-B -u -m backend.local --port 5000` launcher.
Direct `/api/auth/me` returned 401 JSON, not 503. Historical missing
DATABASE_URL/JWT_SECRET_KEY configuration explains the reported 503; that failure
did not recur in this run. The first current failing boundary was TCP connection
to the absent frontend listener, before proxying or Flask authentication.

Started only this workspace's existing Vite on the verified free port, with a
hidden window and local stdout/stderr logs:

```powershell
# Working directory: frontend (equivalent server command)
node node_modules/vite/bin/vite.js --port 5174
```

The actual launch used `Start-Process`, `-WindowStyle Hidden`, the absolute frontend
working directory and `.local/auth/vite.stdout.log` / `vite.stderr.log` redirection.
Final listeners: Vite PID 20844 on 127.0.0.1:5174; existing Flask PID 26200 on
127.0.0.1:5000. No existing process was stopped or restarted. No application code
change was warranted: the earlier targeted local launcher correction is already
present, and fresh requests pass with it. No schema or dependency changes.

Trace confirmed: AuthPage validates/normalizes email and sends email/password only;
AuthProvider uses `/api`; Vite preserves `/api` and proxies to 127.0.0.1:5000;
Flask checks configuration, validates credentials, atomically persists patient/user
with salted scrypt, and login verifies that hash before issuing HS256 JWT. The
client validates login response and retrieves `/auth/me` before setting session
identity. Logout clears in-memory token/identity; server token revocation is still
outside the existing contract.

### Fresh executed results

Frontend working directory:

| Exact command | Result |
| --- | --- |
| `npm test` | 36 passed, 0 failed/skipped; exit 0; 5.450 seconds |
| `npm run build` | Exit 0; Vite 8.3.4; 35 modules; 769 ms |
| `npm run test:auth:live` after Vite startup | 1 passed, 0 failed/skipped; exit 0; 1.859 seconds |

Workspace root:

| Exact command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v` | 97 passed; OK; exit 0; 11.637 seconds |
| `.venv/Scripts/python.exe -B -m pip check` | Exit 0; No broken requirements found |
| `node .local/auth/verify-patient-workflow.mjs` | Exit 0; live proxy/client/workspace/persistence/denial assertions passed |

Initial sandboxed frontend commands failed at Node subprocess creation (`spawn
EPERM`); the initial backend run had 9 temporary-directory permission errors.
Reruns with approved process/temp-file access passed without changing tests or
implementation. These environment errors are separate from application failures.

The local verification script imports existing frontend modules and creates
synthetic credentials only in memory. Its safe request evidence is
`.local/auth/patient-workflow-evidence.json`, explicitly `browserVerified: false`.
It verified registration 201, login 200, bearer `/me` 200, own profile 200, saving
exactly 12 inputs with notes 201, history/detail 200, logout and protected-route
resolver redirects, anonymous patient reads 401, incorrect credentials 401, and
fresh-client login/retrieval of the saved assessment. A second synthetic owner
received 404 for the first owner's profile/history/detail and assessment write.
Complete backend/frontend suites additionally passed doctor/admin read/write
denials and blocked review actions using disposable fixtures; no live staff
accounts or grants were created.

Read-only SQLite inspection independently confirmed synthetic user 6, its stored
`scrypt:32768:8:1` hash, owner-linked patient 6, and assessment 3 with all 12 JSON
inputs, notes and authenticated recording-user attribution. A fresh client also
retrieved that same assessment. The successful live checks leave three new
synthetic patient accounts total (one from the existing auth check, two from the
patient check) and one assessment in the dedicated local database. No real patient
data was used or removed. The local script/evidence and Vite logs are verification
artifacts, not additional application features.

### Browser evidence remains unavailable

`cua.getState()` returned `apps: []`, `browsers: []`; attempting
`cua.createBrowserTab('iab', 'http://localhost:5174', {visible:true})` returned
`Browser is not available: iab`. Native computer APIs are disabled in this session.
No mounted browser was operated. Missing evidence is actual form typing/submission,
rendered registration success and login errors, browser hash navigation to profile,
form/history/detail, visible saved assessment values, logout clicks and protected
route redirects. Component rendering/handler tests, live HTTP and route-resolver
assertions do not substitute for that evidence. The complete browser journey
therefore remains **unverified**, and this follow-up does not declare browser
acceptance or a newly reproduced 503 fixed.

Only this existing report was updated; no new system map or application code was
written. V17 artifacts, training source, loading controls, watchdog and Docker
resources were untouched. Model loading remains blocked. No receptionist,
appointment, prediction or doctor-access feature work was undertaken.
