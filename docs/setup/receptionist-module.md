# Receptionist administration slice — 14 October 2026

Implemented the approved receptionist identity, exact-email lookup, appointments,
attendance state machine and protected React dashboard. **The full module remains
incomplete: registration invitations are isolated pending a configured dedicated
email delivery service.** No invitation token, setup URL or password-setup endpoint
was introduced. The dashboard explicitly reports invitations as unavailable.

## Policy and implementation

`receptionist` is the fourth role, seeded as ID 4 by additive migration
`0006_receptionist_appointments` after unchanged 0005. Public registration remains
patient-only; trusted local operators use the existing `create-privileged-user`
CLI with `--role receptionist`. JWT authentication reloads roles as before.
Every reception endpoint requires receptionist role. Patient, doctor and admin
accounts cannot use these endpoints. No clinical or grant-management bypass exists.

Exact-email lookup uses the existing canonicalization/validation and account lookup,
not substring search. Response fields are exactly `id`, `email`,
`administrative_status`; the latter derives `registered` from existing credentials
or `credential_setup_required` for a legacy account lacking a password hash. No
demographics, clinical fields, password or hash is serialized. Ambiguous emails,
nonpatient accounts and absent profiles fail closed. A bounded doctor directory
exposes only ID/email for manual selection, not inferred doctor availability.

Appointment creation validates the actual patient owner role and doctor role/account,
not frontend claims. Client cannot select creator/status/audit fields. Default
duration is 30 minutes; explicit end is accepted if strictly after start. Timestamps
require an explicit timezone offset or Z and whole-second precision, normalize to
UTC and are stored as timezone-naive UTC (matching grant timestamp conventions).
API responses append Z. The UI uses device-local datetime fields and labels that
timezone convention, converting to UTC for requests. No clinic hours, recurring
availability, future-only restriction, cancellation deadline or extra duration rule
was invented. Availability is manually confirmed by staff.

Active means `scheduled` or `checked_in`. Intervals are half-open: adjacent bookings
are permitted; any overlap for the same patient OR doctor is rejected. Every booking
mutation first locks the seeded singleton `appointment_lock` via a transactional
UPDATE. SQLite serializes writers; InnoDB holds the same row lock until commit.
Overlap and appointment-state reads follow that lock; MySQL overlap/state reads
also use FOR UPDATE for current reads. This provides application transaction-level
serialization, not a claim that privileged raw SQL cannot bypass booking policy.
The SQLite concurrency test executes actual simultaneous requests and verifies one
201, one 409 and exactly one appointment. Live MySQL concurrency remains untested.

Allowed transitions are exactly scheduled → checked_in/cancelled/no_show and
checked_in → completed. Completed, cancelled and no_show are terminal. Only scheduled
appointments may be rescheduled. All receptionists may manage all appointments;
there is no creator ownership gate. Each successful creation/reschedule/transition
persists actor, time, states and the corresponding time interval in AppointmentEvent.
Appointment CRUD does not create or change a patient–doctor grant. No appointment
deletion or clinical/review operation is provided.

## Endpoints and UI

All new endpoints are under `/api/reception`, use existing JSON errors, bearer role
checks and Cache-Control no-store. Lists paginate by bounded `after_id`, 50 rows.

| Method/path | Contract |
| --- | --- |
| GET `/patients?email=...` | Exact-email lookup; `{patient:{id,email,administrative_status}}` |
| GET `/doctors` | `{doctors:[{id,email}],next_after_id}`; manual selection |
| GET `/appointments` | Administrative booking list/status/actor/time fields; no clinical data |
| POST `/appointments` | Required patient_id, doctor_user_id, starts_at; optional ends_at; 201 `{appointment}` |
| POST `/appointments/{id}/reschedule` | starts_at and optional ends_at; scheduled-only; 200 or 409 |
| POST `/appointments/{id}/status` | Exactly `{status}`; approved transitions only; 200 or 409 |

Existing protected hash route `#/receptionist` uses ReceptionPage inside Router and
AppShell. Login role labels/session parsing recognize receptionist; navigation
points to Reception desk. Dashboard supports lookup, manual doctor/time selection,
booking, reschedule, check-in, completion, cancellation, no-show, pagination,
loading/errors and refresh. Terminal appointments expose no mutation buttons.
Patient screens/routes and frontend port configuration remain unchanged. No new
frontend/backend dependency was installed.

## Invitation blocker and approved future security contract

Policy is settled: lifetime exactly 24 hours; dedicated configured delivery service
emails only the patient; secure single-use random token; persist only its hash;
atomic consumption after patient-chosen/confirmed password setup using existing
hashing; reject expired/invalid/used tokens and existing accounts; receptionist
receives status only, never raw token/full setup URL in any response, UI, log or
audit. The future setup link needs no-cache handling and secret-safe access logging.

No invitation/token service or configured email delivery integration exists in the
application. Required integration is an approved delivery service/provider, sender
identity/credentials, and patient-facing setup-link destination/configuration. No
provider, credential defaults, SMTP host or delivery-success fallback was invented.
Invitation issuance/setup/status APIs and UI controls are not enabled; no tokens
were generated, saved or exposed. Therefore invitation creation, expiry, delivery,
password setup and duplicate/consumption tests remain pending for that isolated
subfeature. Existing self-registration validation/duplicate/password tests still
pass. A provider failure must not expose a link to reception or report success.

## Migration and actual development database

0006 broadens the existing role CHECK, seeds receptionist, creates appointments,
appointment_events and a singleton booking-lock table with required FKs, indexes,
status/duration constraints. Prior migrations, 0005 grants and review blockers were
not modified. Downgrade refuses to remove the role while receptionist accounts exist.

SQLite needs a referenced role-table CHECK rebuild. The initial disposable fixture
demonstrated that deferred foreign keys do not permit dropping the referenced role
table. The corrected migration uses a dedicated fresh SQLite connection with FK
checks temporarily off, explicitly begins a transaction before rebuilding, preserves
all rows and checks foreign_key_check before completion. The existing database
extension now restores FK enforcement at pool check-in after commit/rollback; runtime
requests continue to enforce FKs. A caller already writing with FK enforcement on
and existing users is rejected rather than committing its transaction implicitly.
This follows [Alembic batch migration guidance](https://alembic.sqlalchemy.org/en/latest/batch.html).
Only the role table is rebuilt through Alembic; the persistent database is not reset
or recreated. Tests verify schema agreement and runtime FK enforcement restoration.

Approved target: `.local/auth/auth.sqlite3`, local development SQLite. A consistent
SQLite backup was created and verified BEFORE stopping the app/migrating:

`.local/backups/auth-before-0006-20261014-004628.sqlite3`

Backup/source integrity ok; all table counts and row hashes matched at revision
0005. Before synthetic tests: 11 users, 9 patients, 4 assessments, 2 grants and 1
grant-administrator permission. Applied 0005 → **0006_receptionist_appointments**
using the existing Alembic supplied-connection workflow. Every original row,
including grants and clinical data, exactly matched the backup afterward. Integrity
and foreign-key checks passed. Backup and original remain preserved.

Rechecked intended listener 21836/parent 22568 against the project venv and local
launcher command, stopped only that backend for migration/reload and restarted the
same hidden-window `-B -u -m backend.local --port 5000` launcher. Final listener
**6720**, parent **26964**; one backend listener only. Frontends unchanged:
5173/PID 27788 and 5174/PID 20844. Helpers/logs/evidence are in `.local/reception`.

## Executed evidence and exact commands

| Command / working directory | Actual final result |
| --- | --- |
| Root: `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_reception.py' -v` | 10 passed; exit 0; 1.814 seconds |
| Root: `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v` | 123 passed; exit 0; 36.479 seconds; auth/patient/grant/review regressions included |
| Frontend: `npm test` | 39 passed, 0 failed/skipped; exit 0; 4.305 seconds |
| Frontend: `npm run build` | Exit 0; 37 modules; 257 ms |
| Root: `.venv/Scripts/python.exe -B -m pip check` | Exit 0; No broken requirements found |
| Root: `.venv/Scripts/python.exe -B .local/reception/database_acceptance.py` | Exit 0; consistent verified backup |
| Root: `.venv/Scripts/python.exe -B .local/reception/database_acceptance.py migrate` | Exit 0; revision 0006; original rows and integrity/FKs preserved |
| Root: `.venv/Scripts/python.exe -B .local/reception/live_acceptance.py` | Final exit 0; actual persistent SQLite and HTTP checks PASS through 127.0.0.1:5173 |

Automated backend checks cover receptionist provisioning, denied public role
injection, all unauthorized roles, exact lookup privacy, timestamps, default and
explicit duration, both conflict dimensions, adjacency/terminal slot release,
actual concurrent file-backed SQLite bookings, every allowed/forbidden transition,
rescheduling by another receptionist, post-check-in restrictions, actual migration
with existing patient references, FK restoration and metadata agreement. Frontend
checks cover route guards, bearer/email/error contracts, malformed responses,
rendered allowed actions and terminal/loading/error states. Existing real disposable
Flask/Vite patient/auth integration tests pass with receptionist included in auth.

Live HTTP: synthetic patients register/login/profile 201/200; reception lookup 200
with exactly three fields and wrong email 404; booking 201; doctor and patient
overlap 409; second receptionist reschedule/check-in/complete 200; post-check-in
reschedule/cancel 409; terminal transition 409; cancellation/no-show 200. Patient
and doctor reception-list access 403; missing bearer 401. Receptionist patient
profile, clinical history/detail/write and grant-list/issue/revoke all 403; review
path 404. Existing patient assessment creation/history/detail still returns 201/200.
Read-only SQL verifies original rows, terminal statuses and eight audit events per
synthetic run. Safe method/path/status evidence: `.local/reception/live-evidence.json`.

The first live helper incorrectly expected nine audit events rather than eight;
all preceding HTTP assertions passed. Corrected the helper expectation and reran
successfully without application changes. Two synthetic runs leave 12 new users,
4 patients, 2 assessments, 6 terminal appointments and 16 appointment events. No
credential was printed/saved. No supported delete endpoint exists; records and audit
history are retained. Existing records were not modified/removed to make tests pass.

Browser inventory `cua.getState()` returned no apps/browsers. No mounted browser,
visual/focus interaction or browser click-through acceptance is claimed. Live MySQL
was not tested. Invitations remain a delivery integration blocker; this is accepted
role/lookup/booking behavior, **not a completed invitation/full receptionist module**.
V17, dataset, inference/runtime/loading, Docker/WSL, dependencies, grant policy and
review-write blockers remain untouched. No Git repository/diff/commit claim.

## Files

Created: `backend/app/models/appointment.py`,
`backend/migrations/versions/0006_receptionist_appointments.py`,
`backend/app/api/reception.py`, `tests/backend/test_reception.py`,
`frontend/src/services/reception.js`, `frontend/src/pages/ReceptionPage.jsx`,
`frontend/tests/reception.test.js`, this report; local acceptance helpers/evidence.

Modified: backend model registration, provisioning CLI, API registration and
database pool FK restoration; frontend AuthContext, auth role labels, routes and
Router; backend auth/database/route-inventory/grant-denial tests; frontend role
guard/Flask fixture/auth-contract tests; existing system map and implementation
checklist. Existing patient pages, grant implementation/migration 0005 and review
implementation/migration 0004 were unchanged.

Exact modified paths: `backend/app/models/__init__.py`,
`backend/app/auth/__init__.py`, `backend/app/api/__init__.py`,
`backend/app/database/__init__.py`, `frontend/src/auth/AuthContext.jsx`,
`frontend/src/services/auth.js`, `frontend/src/routing/routes.js`,
`frontend/src/routing/Router.jsx`, `tests/backend/test_auth.py`,
`tests/backend/test_database.py`, `tests/backend/test_foundation.py`,
`tests/backend/test_access_grants.py`, `frontend/tests/foundation.test.js`,
`frontend/tests/flask_auth_fixture.py`, `frontend/tests/flask-contract.test.js`,
`docs/architecture/ayursage-system-map.md`, `docs/setup/implementation-checklist.md`.
