# Database foundation - 13 October 2026 (Asia/Calcutta)

Historical milestone record. Subsequent authentication changes and the second
migration are documented in [authentication.md](authentication.md).

This milestone adds persistence only. `/api/health` remains the only API route.
No authentication, authorization endpoints, clinical validation, inference, frontend,
reports or deployment is implemented. Watchdog Step 1.3 remains NOT ACCEPTED and
deferred. V17 loading remains disabled; no ML or watchdog files were edited.

## Inspection and design

Inspected the backend factory, configuration, routes, errors, dependency files,
all existing backend tests, README, architecture, implementation checklist,
verification documentation, environment template and ignore rules. Reserved
database/model/migration directories were empty: no existing SQLAlchemy or Alembic
support could be reused. No applicable AGENTS.md or Git repository was found.
Baseline: 13 backend tests passed; pip check reported no broken requirements.

The shared `db` extension is initialized only when a database URL is configured.
It scopes sessions to the Flask application context. Startup neither connects to
the database nor creates/upgrades tables. Schema changes use Alembic explicitly,
not `create_all()`. The health response continues to indicate liveness only.

| Table | Minimum stored data / constraints |
| --- | --- |
| roles | Unique required code restricted to patient, doctor, admin; migration seeds these three roles |
| users | Unique required email and required role FK; no login credentials or seeded accounts |
| patients | Required unique owner user FK (one patient profile per owner) |
| clinical_assessments | Required patient and recording-user FKs, database-clock creation timestamp, optional manual notes |

All parent links use RESTRICT deletion; no automatic record deletion cascades.
Relationship foreign keys are indexed or unique. MySQL tables specify InnoDB and
utf8mb4. MySQL CHECK constraint enforcement requires MySQL 8.0.16 or newer;
no live MySQL server/version has been verified in this milestone.
Email normalization and database collation behavior must be resolved with future
account work; there is no login behavior here. Timestamps use the database clock,
without claiming UTC conversion; production timezone policy remains future work.

Foreign keys establish identity links, not role checks or access grants. Future
APIs must authenticate the actor, verify that a patient owner has the patient role,
scope patient access to the owner, and enforce the approved doctor access rules
before reading/writing data. A doctor role or recording-user link alone must not
grant access to all patients. Administrator access also requires explicit API policy.
No doctor assignment/access-grant scheme is invented in this milestone.
There are no clinical ranges, medical decisions, ML inputs/outputs or care-plan fields.

## Configuration and migration use

Read process environment only; no automatic `.env` loading or credential fallback.
`DATABASE_URL` absent/blank disables database initialization. Supported drivers:
`mysql+pymysql` with a database name, or `sqlite` / `sqlite+pysqlite` with an absolute
file path or `:memory:`. Relative SQLite paths are rejected so Flask and Alembic
cannot silently address different files. Malformed/unsupported URLs fail with a
generic configuration error without echoing credentials. SQL parameters are hidden
in engine errors. Real credentials belong in injected environment variables.

Tests can override `SQLALCHEMY_DATABASE_URI` with `sqlite:///:memory:` via
`create_app(test_config)`. SQLite foreign key enforcement is enabled on every new
connection. Alembic can accept a supplied test connection; normal CLI migrations
require `DATABASE_URL` and never default to a cloud database.

From the workspace root, after setting DATABASE_URL to the intended database:

```powershell
.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini current
.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini check
```

These are usage instructions, not claims of executed CLI migrations. Downgrading
to base drops all four application tables and their data; round-trip tests use
only disposable databases. Database connection/migration errors propagate to the
caller; failures are not reported as success. No database API handlers were added.

The extension follows the official [Flask-SQLAlchemy factory setup](https://flask-sqlalchemy.palletsprojects.com/en/stable/quickstart/).
Migration structure follows the [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
SQLite FK setup and MySQL table options follow the official
[SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) and
[MySQL](https://docs.sqlalchemy.org/en/20/dialects/mysql.html) dialect documentation.

## Executed verification

Exact commands from the workspace root:

```powershell
# Baseline and post-implementation suite (same command)
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
# Install command, retried with approved network/environment access
.venv/Scripts/python.exe -m pip install Flask-SQLAlchemy==3.1.1 'SQLAlchemy>=2.0,<2.1' 'alembic>=1.18,<2' 'PyMySQL>=1.1,<1.2'
```

Installation succeeded in project-local `.venv`; existing Flask pins were retained.
Added direct pins: Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.54, Alembic 1.20.0,
PyMySQL 1.1.3. Added transitives: greenlet 3.5.6, Mako 1.4.3,
typing_extensions 4.16.0. Both requirement files reflect the installed versions.
The initial restricted install reported no matching Flask-SQLAlchemy distribution;
the approved retry succeeded. No global Python environment was modified.

Initial post-change suite: 31 tests, one error in the file-database test because
Windows sandbox ACLs denied access/cleanup of a disposable temporary directory.
The approved retry passed all 31 tests (0.277 seconds, exit 0): original 13 plus
18 database tests. A fixture autoflush warning was removed before the passing run.

The tests executed Alembic upgrade head, repeated upgrade, downgrade base and
reupgrade against isolated SQLite, including an environment-configured file DB.
They verified role seeds, model/schema agreement through Alembic compare_metadata,
relationships, uniqueness, required fields, foreign keys, deletion restrictions,
rollback/reuse after failed writes, app isolation, missing URL failure,
malformed URL handling, no startup connection/schema creation and unmigrated
database failure. Offline MySQL upgrade SQL was generated in memory and checked
for table creation, InnoDB and RESTRICT clauses; it was not applied to MySQL.

After tightening SQLite URL validation to reject hosts/credentials, the final
approved suite rerun passed all 31 tests in 0.309 seconds, exit 0. No warnings.

Additional executed commands:

```powershell
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
.venv/Scripts/python.exe -B -c "import importlib.metadata as m,pathlib; entries=pathlib.Path('backend/requirements.txt').read_text().splitlines(); assert all(m.version(line.split('==')[0])==line.split('==')[1] for line in entries if line and not line.startswith('#')); print('All pinned runtime versions match installed distributions')"
.venv/Scripts/python.exe -B -c "import hashlib,json,pathlib; roots=['ml','infra','tests/integration','tests/ml','frontend']; print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in roots for p in pathlib.Path(root).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','.venv','__pycache__','.npm-cache'))}))"
```

Results: pip check exited 0 with `No broken requirements found`; route discovery
exited 0 listing only `api.health GET /api/health`; installed-pin comparison exited
0 with all pins matching. SHA-256 inventory was captured before and after editing,
then compared: all 18 existing inventoried files remained identical, no added or
removed files in those roots. This includes the V17 production model, training
source, dataset, inference controls, infrastructure/watchdog scripts, ML/integration
tests and frontend manifests. Environments, bytecode and frontend caches were
excluded. The empty workspace temporary directory left by the failed sandbox test
was checked and removed by an approved nonrecursive cleanup.

## Changed files

Existing files updated:

- `backend/app/__init__.py`
- `backend/config/__init__.py`
- `backend/requirements.in`
- `backend/requirements.txt`
- `.env.example`
- `README.md`
- `docs/architecture/overview.md`
- `docs/setup/implementation-checklist.md`

New files:

- `backend/app/database/__init__.py`
- `backend/app/models/__init__.py`
- `backend/alembic.ini`
- `backend/migrations/env.py`
- `backend/migrations/script.py.mako`
- `backend/migrations/versions/0001_database_foundation.py`
- `tests/backend/test_database.py`
- `docs/setup/database-foundation.md`

The ignored project-local `.venv` received database dependencies. No Git diff,
tracked-file status, commit or secret-scanning result is claimed: this workspace
has no Git repository. No credentials were added to project files.

Not performed: live MySQL connection/migration/constraints, production/cloud
migrations, CLI upgrade/current/check, clean-environment installation, Docker or
deployment checks, authentication/access-control tests, frontend, ML or watchdog
integration suites. These are outside this milestone or require a configured
server. No production database credentials were requested or used.
