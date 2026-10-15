# AYUR-SAGE

AI-Based Ayurvedic Treatment and Diet Recommendation System.

Flask backend, database foundation and JWT authentication. `GET /api/health` returns `{"status":"ok"}`.
Users/roles, patients and clinical assessment persistence have an initial Alembic
migration. Patient signup, login, authenticated identity and reusable role/ownership
helpers are implemented. Patient profile and clinical assessment creation/retrieval
are implemented for authenticated owners. Doctor access remains denied pending
explicit grants; inference remains unimplemented.
See [authentication setup and verification](docs/setup/authentication.md).
See [patient API setup and verification](docs/setup/patient-assessment-apis.md).
Assessment review state/history foundations are implemented, but decision writes
and review endpoints remain blocked pending explicit grants and review policy.
See [review foundation verification](docs/setup/assessment-review-foundation.md).
The React/Vite/JavaScript/Bootstrap frontend supports accounts, own patient profiles,
clinical assessment entry and assessment history/detail. It calls one modular Flask
REST API backed by MySQL via SQLAlchemy. V17 inference remains planned and disabled.
See [Patient Assessment UI verification](docs/setup/patient-assessment-ui.md).
See docs/architecture/overview.md.

## Local authentication debugging

For the local debugging session at `http://localhost:5174`, use the explicit
SQLite-backed launcher from the workspace root:

```powershell
.venv/Scripts/python.exe -B -m backend.local --port 5000
```

It prepares a dedicated local database and generated signing key in `.local/auth/`
using the existing migrations. Accounts/key persist across restarts. The frontend's
existing `/api` proxy targets this backend. Keep the frontend on port 5174 with
`npm run dev -- --port 5174` when restarting it. This is an opt-in local workflow;
the standard backend startup below still requires environment-supplied database/JWT
configuration and explicit migrations. Health 200 alone does not imply auth readiness.
See [authentication failure diagnosis and verification](docs/setup/authentication-failure-fix.md).

For restarts in VS Code, **Terminal > Run Task** provides `AYUR-SAGE: local auth
backend (5000)` and `AYUR-SAGE: frontend (5174)`. Start each only when its port is
free; these tasks do not stop other processes. `flask --app backend.app run` does
not use the local launcher's database or key and returns auth 503 without its own
environment configuration. After starting both servers, run `npm run test:auth:live`
from `frontend` to check the actual port 5174 proxy and authentication. This opt-in
check creates one synthetic patient account, prints no credentials/tokens, and
does not exercise browser clicks. See the [recurrence evidence](docs/setup/authentication-runtime-repair.md).

## Run and test the backend

From the workspace root, using an isolated Python environment:

```sh
python -m pip install -r backend/requirements.txt
python -m pip check
python -m unittest discover -s tests/backend -p "test_*.py" -v
python -m backend
```

For Windows, create `.venv` with `python -m venv .venv` and use
`.venv/Scripts/python.exe` in place of `python`. The development server binds to
`127.0.0.1`, using `BACKEND_PORT` (default 5000). Set environment variables before
starting it; for example, PowerShell: `$env:BACKEND_PORT = '5100'`.
The factory is also discoverable via `python -m flask --app backend.app routes`.
This local server is not a production deployment.

Configuration reads the process environment, without automatically loading `.env`.
`FLASK_DEBUG` defaults to off; accepted values are blank, 0, 1, false and true
(case-insensitive). Enable it only for local development. `SECRET_KEY` has no
fallback and remains optional because Flask cookie sessions are not used.
Authentication requires a separate environment-supplied `JWT_SECRET_KEY` and a
migrated database. Without those, auth endpoints return generic 503 responses and
health remains available. `JWT_ACCESS_TOKEN_SECONDS` defaults to 900 (15 minutes).
`DATABASE_URL` enables the database extension; blank leaves it disabled. No
connection or schema creation occurs at startup. Migrations must be run explicitly.
See [database setup and verification](docs/setup/database-foundation.md).
Frontend variables are configured separately in `frontend/.env.local`; see
[frontend setup and verification](docs/setup/frontend-foundation.md). V17 variables
remain unused.
Never put secrets in Vite variables. The health route checks application liveness
only, not MySQL, cloud storage or model readiness.

## Run and test the frontend

See [frontend setup](docs/setup/frontend-foundation.md) and
[Patient Assessment UI contracts and verification](docs/setup/patient-assessment-ui.md).
The existing locked dependencies are reused; no new packages are required.

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
npm test
npm run build
```

Vite serves at `http://127.0.0.1:5173`. Start the configured/migrated Flask backend
separately using the instructions above. `VITE_API_BASE_URL=/api` and
`FLASK_API_PROXY_TARGET=http://127.0.0.1:5000` connect through Vite's local development
proxy. Public registration creates patients only; provision doctors/administrators
through the existing trusted backend CLI. Tokens stay in memory: reloads require
sign-in, and logout clears this tab's state. Flask remains responsible for all
resource authorization. Patients can view/create their own profile, save all 12
assessment inputs with optional notes, and view paginated history and details.
Saving an assessment does not generate predictions yet.

## Development container

The historical Phase 1 record describes a development container, but `.devcontainer/`
is absent from the workspace inspected on 12 October 2026. The instructions below
require restoring its verified configuration in separately authorized work; the
current backend can be tested in the local Python environment described above.

Use Docker Desktop with its Linux container engine, VS Code and the Microsoft
Dev Containers extension (`ms-vscode-remote.remote-containers`). Open this workspace
and select **Dev Containers: Reopen in Container**. The Dockerfile pins official
Python 3.12 and Node 24 images by digest; exact measured versions and checks are in
docs/setup/verification.md. V17 compatibility remains unverified.

The entire workspace is bind-mounted at `/workspaces/ayur-sage`: changes there are
shared with the Windows host, including dependency files. The Python environment
at `/opt/venv` is container-local and recreated on rebuild. No Docker socket or
existing Docker volume is mounted. The container uses a non-root developer user.
The build context is only `.devcontainer`, excluding project secrets and assets.

Inside the container, install the locked dependencies explicitly:

```sh
python -m pip install -r backend/requirements.txt
python -m pip check
cd frontend
npm ci
```

Do not share Windows-installed `node_modules` with Linux tooling: run `npm ci` again
when switching platforms. Use the backend start command above for Phase 2.

There are no published ports. Configure `containerEnv.BACKEND_PORT` and
`containerEnv.FRONTEND_PORT` in devcontainer.json when services are implemented;
add matching ports to `forwardPorts`, or use VS Code's Ports panel. Applications
read `BACKEND_PORT` in the local entry point; Vite frontend configuration is
documented in docs/setup/frontend-foundation.md.
`.env.example` documents configuration; it is not automatically loaded or injected.
Keep real values in ignored local
files and never place secrets in Vite variables, which are public client config.

## Minimal dependencies

Flask, Flask-SQLAlchemy, SQLAlchemy, Alembic, PyMySQL and PyJWT are the direct backend
dependencies; resolved runtime dependencies are pinned in requirements.txt.
Tests use Python's built-in unittest, so no additional
test dependency is needed. React and React DOM provide the account UI,
Bootstrap provides styling, Vite provides development/build tooling, and the React
plugin supplies React integration. Werkzeug supplies password hashing. No ML, PDF or cloud packages are installed
in advance. npm generates package-lock.json; do not edit it manually.

Official requirements: https://flask.palletsprojects.com/en/stable/installation/
and https://vite.dev/guide/. Image digests are deliberately fixed; upgrades require
explicit review and repeated verification. Locked versions are not a security audit.

## Structure and next steps

`frontend/` contains account/patient screens, API/auth services, routing and tests; `backend/` Flask foundation and reserved layers/migrations;
`ml/` inference, clinical engines, schemas and artifact instructions; `docs/`
architecture, API and setup records; `tests/` backend, ML and integration folders;
`infra/docker/` is reserved for later infrastructure. Empty directories are not
retained by Git; future folders remain empty. Git is not initialized.

See docs/setup/implementation-checklist.md and docs/setup/verification.md for phase
gates. Obtain the approved V17 bundle through controlled transfer before model work.
The Patient Assessment UI is the current completed milestone. Doctor grants, review
actions, inference and further integrations remain deferred to separately authorized work.
