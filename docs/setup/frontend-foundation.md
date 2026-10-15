# Frontend foundation — 13 October 2026 (Asia/Calcutta)

The existing `frontend/` dependency foundation was reused. It contained package.json,
package-lock.json, installed dependencies and empty src/public folders, with no
application implementation. No duplicate frontend or new npm dependency was added.
Node v24.16.0 / npm 11.13.0 were used. No applicable AGENTS.md was found. The workspace
has no Git repository, so this report does not claim a Git diff or tracked status.

## Implemented scope

React, Vite, JavaScript and Bootstrap supply a responsive account shell, patient
registration, login for existing patient/doctor/administrator accounts, role-specific
account homes, logout, loading feedback and accessible validation/error messages.
`src/pages`, `components`, `services`, `auth` and `routing` separate responsibilities.
Small hash-based routing uses the browser hashchange API; no router package or server
fallback configuration is needed. Anonymous role routes redirect to login; navigating
to a different role's home displays Access restricted. This is UI navigation only:
Flask JWT/RBAC/ownership checks remain authoritative on every API request. The current
role is obtained from `/auth/me`, never from decoded JWT claims or client input.

No clinical dashboard, patient-data controls, doctor grants, review actions, model
loading, prediction results, PDF reports, deployment or new backend endpoints were
implemented. All account homes are foundation screens. V17/Phase 2A/2B and review
policy blockers remain unchanged. Work stops at this milestone.

## Configuration and local use

Start the separately configured and migrated Flask application as documented in
README.md and authentication.md. From the workspace root:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

`npm ci` and copying the example are setup instructions, not commands executed during
this milestone. Existing installed locked dependencies were reused.

Vite loads `frontend/.env.local` automatically (the root backend example is separate).
The defaults/example use:

```dotenv
VITE_API_BASE_URL=/api
FRONTEND_PORT=5173
FLASK_API_PROXY_TARGET=http://127.0.0.1:5000
```

Open `http://127.0.0.1:5173`. Set FLASK_API_PROXY_TARGET to match BACKEND_PORT if Flask
uses another port. VITE_API_BASE_URL includes the `/api` prefix; service paths append
`/auth/register`, `/auth/login` and `/auth/me`. An absolute HTTP(S) API URL is supported
but requires appropriate backend CORS configuration, which was not added. The local
Vite proxy avoids that requirement. Vite dev binds loopback with a strict configured
port. VITE_* values are public build-time configuration; never put credentials in
those values. Changing them requires restarting Vite/rebuilding the static bundle.
The development proxy is not included in build output or provided by `vite preview`;
serving a build with relative `/api` requires an explicitly configured same-origin API
reverse proxy in a later deployment milestone.

Tokens exist only in memory, never in storage, URLs or logs. Reloading or opening a
new tab requires login. Login resolves `/me` before establishing an authenticated UI.
Expiry and authenticated 401 responses clear token/user state and request sign-in;
a wrong-password 401 displays a credentials error without expiring another session.
Logout clears local identity/token and the expiry timer. There is no backend revocation
endpoint: a previously issued token remains valid on the server until expiry. API
requests omit cookies, disable cache, reject redirects and use bearer authorization
only for authenticated requests. The existing short token lifetime is respected;
there is no refresh-token flow.

## Inspected Flask contract

Inspected backend/app/auth/routes.py, auth/security.py, errors.py, app/__init__.py,
patient routes and existing auth tests before wiring the forms.

| Operation | Request | Successful response |
| --- | --- | --- |
| POST /api/auth/register | email/password only | 201 `{user: {id, email, role}}`; patient only |
| POST /api/auth/login | email/password only | 200 `{access_token, token_type: "Bearer", expires_in}` |
| GET /api/auth/me | Authorization: Bearer | 200 `{user: {id, email, role}}` |

Backend role codes are patient, doctor and admin. Privileged registration is not a
public operation; trusted operators use the existing CLI. Registration does not log
the user in automatically; success links to sign-in. Backend errors are
`{error: {code, message}}`, with generic HTTP names and no field-error map. The client
maps HTTP status to safe consistent UI messages; it handles network errors and
non-JSON proxy responses without echoing arbitrary response content. It validates
successful auth schemas and fails closed on unknown roles.

Form validation matches inspected email normalization/syntax, local/total length,
password lengths (12–128 registration; 1–128 login), nonblank and no NUL requirements.
Unicode password length is counted in code points to match Python. Confirmation is
client-only and never sent. Backend validation remains authoritative.

## Executed checks and exact commands

From `C:\Users\yvasa\Videos\PROJECT-Ayursage\frontend`:

```powershell
npm run build
npm test
npm ls --depth=0
```

Final build: exit 0, Vite 8.3.4, 27 modules transformed, 352 ms. Output: dist/index.html,
231.24 kB CSS (31.21 kB gzip), 232.96 kB JS (73.20 kB gzip).
Final tests: exit 0, **13 passed, 0 failed/skipped**, 2.589 seconds.
Dependency check: exit 0; unchanged installed React 19.3.0, React DOM 19.3.0,
Bootstrap 5.3.8, Vite 8.3.4 and React plugin 6.1.2.

The first build attempt failed with sandbox `spawn EPERM` in Vite's Windows path
resolver. Repeating with approved normal process access succeeded. Final build/tests
used that access; no code workaround or dependency upgrade was needed. Earlier test
runs passed 9 and then 13 checks; the final 13-check run includes the proxy verification.

Tests use Node's built-in test runner, React's existing server renderer and Vite.
They cover validation boundaries, all role-route combinations, exact credential
bodies and URLs, bearer headers, /me role resolution, safe error handling, stale 401s,
malformed success/unknown roles, session expiry, logout/cleanup, pending-login
cancellation, duplicate-login suppression, rendered form/navigation/status markup.
The HTTP test starts an isolated loopback Flask fixture with an in-memory SQLite
schema migrated to head and disposable privileged accounts; no production database,
credentials or persistent accounts are used. It starts Vite on an ephemeral loopback
port, verifies HTML and transformed JSX responses, and exercises real registration,
duplicate registration, privilege-field rejection, wrong password, login/me for all
three roles, logout/token clearing and server-side privileged patient-access denial
through the Vite proxy. Both servers are stopped by test cleanup.
The fixture uses the root `.venv`; AYURSAGE_TEST_PYTHON can select another interpreter
with the existing backend requirements. npm test therefore needs both environments.

From the workspace root, backend regressions were also executed despite no backend
source edits:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

All exit 0: **93 tests passed in 15.381 seconds**, `No broken requirements found`,
and the same 10 route operations. SHA-256 inventories before/after implementation
compared all 52 non-bytecode files in backend, ml, infra, tests/backend, tests/ml and
tests/integration: zero changes/additions/removals. The temporary inventory was
removed after comparison. No protected migrations, V17 assets/training/loading
controls, watchdog files or Docker resources were edited.

## Changed files

Updated:

- README.md
- frontend/package.json (description and scripts only)

Added:

- docs/setup/frontend-foundation.md
- frontend/.env.example
- frontend/index.html
- frontend/vite.config.js
- frontend/src/main.jsx
- frontend/src/styles.css
- frontend/src/auth/AuthContext.jsx
- frontend/src/auth/session.js
- frontend/src/auth/validation.js
- frontend/src/components/AppShell.jsx
- frontend/src/components/Loading.jsx
- frontend/src/pages/AuthPage.jsx
- frontend/src/pages/HomePage.jsx
- frontend/src/routing/Router.jsx
- frontend/src/routing/routes.js
- frontend/src/services/api.js
- frontend/src/services/auth.js
- frontend/tests/foundation.test.js
- frontend/tests/flask-contract.test.js
- frontend/tests/flask_auth_fixture.py
- frontend/tests/render.test.js
- frontend/tests/session.test.js

Generated ignored output: frontend/dist/ and Vite local cache/temporary files under
node_modules. package-lock.json, backend files and .gitignore were not edited.

## Not tested

No browser surface was available: creating the in-app browser returned
`Browser is not available: iab`, and the browser inventory was empty. Interactive
browser clicks, visual/responsive screenshots, focus behavior and assistive-technology
behavior were not verified. React server-rendered markup and HTTP/proxy checks passed,
but do not replace those checks. No clean install, live MySQL, external-origin CORS,
production static hosting/proxy, Docker/cloud deployment, PDF, V17 loading/inference
or watchdog acceptance checks were performed. No real user data was accessed.
