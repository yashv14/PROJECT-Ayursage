# Patient–doctor assessment-read grants

16 October extension: [clinical-review permission](doctor-clinical-review.md) is an
explicit opt-in at issuance; existing assessment-read grants remain read-only.
Revocation removes both permissions. The policy below records the original milestone.

13 October 2026 (Asia/Calcutta). Backend implementation of the explicitly approved
policy; no doctor UI, assessment writes, review actions, prescriptions or ML.

## Policy and consent representation

Only an authenticated `admin` with an explicit `GrantAdministrator` permission can
issue a grant. Existing admins receive no permission automatically. The trusted
local operator authorizes an existing administrator through the existing Flask CLI
convention. This permission does not allow clinical-record reads.

Issuance requires `consent_reference`: a nonblank, bounded (256 characters) opaque
reference to already recorded patient consent. The issuing administrator attests
that the referenced evidence covers the verified patient owner, selected doctor,
assessment-read scope and 30-day duration. The record snapshots owner identity,
doctor identity, issuer, reference and server timestamps together; clinical notes
and review records are not repurposed as consent. Missing references and injected
owner/issuer/scope/status/expiry fields are rejected. The API never fetches a URL or
stores/uploads a consent document. It records the administrator's attestation and
reference, **not independent verification of an external document's authenticity**.
The authorized administrator must retain the referenced consent evidence outside
this API. Document capture, signature verification and patient consent UI are not
implemented or implied.

The server sets scope to `assessment_read`, issuance to UTC and expiry to exactly
30 days later. Timestamps are stored as UTC without timezone in portable DateTime
columns and serialized with `Z`; second precision is intentional for MySQL/SQLite
agreement. Access requires `issued_at <= now < expires_at`, issued status, no
revocation, the correct doctor/patient/consent-owner link and exactly 30-day duration.
Each request re-reads grant columns from the database; no token or session caches
grant authority. No-grant, expired, revoked and invalid grants fail closed with 403.
Nonexistent patient IDs are also 403 for doctors to avoid disclosing existence.

The owning patient or an explicitly authorized administrator can revoke. The first
revoker and timestamp are preserved on repeat requests. Revocation commits before
the response; subsequent reads using the same JWT are denied. An already-running
request is not retroactively cancelled. A replacement grant after expiry/revocation
requires a new consent reference and creates a new history row, never extends or
overwrites the original. Revoking an old historical grant cannot revoke a separate
new grant; the owner can list current/history grant metadata to select it.

## Schema and operations

Migration `0005_patient_doctor_grants`, after untouched `0004_assessment_reviews`,
adds `grant_administrators` and `patient_doctor_grants`. No accounts or permissions
are seeded. Required foreign keys use RESTRICT. Grant rows contain explicit issued
or revoked status, patient, doctor, consent-owner, consent reference, issuer,
issuance/expiry and revoking actor/time. Expired status is derived for responses.
Checks enforce scope, timestamp ordering, revocation consistency and nonblank
consent. Indexed patient/doctor/expiry columns support lookups. A nullable active
slot with a unique patient/doctor/slot constraint prevents duplicate active grants;
expired slots are retired transactionally without rewriting issuance history.
Unique patient/doctor/consent reference prevents reusing the same attestation for
renewal. Application ORM edits/deletes and session bulk updates/deletes are blocked;
the service uses conditional Core updates only for revocation and expired-slot
retirement. This is application protection, not DB-wide tamper-proof auditing:
privileged raw SQL can bypass application guards. No existing general audit system
was found, so grant lifecycle rows provide the milestone's durable audit record.

| Method/path (all under `/api`) | Rule and response |
| --- | --- |
| POST `/patients/{patient_id}/doctor-access-grants` | Explicit grant administrator only; body exactly `{doctor_user_id, consent_reference}`; verifies patient/owner and a password-enabled doctor account; 201 `{grant}`; duplicate active pair/reference 409 |
| GET `/patients/{patient_id}/doctor-access-grants` | Owner or explicit grant administrator; bounded 20-row pagination with `after_id`; `{grants,next_after_id}`; grant metadata only |
| POST `/patients/{patient_id}/doctor-access-grants/{grant_id}/revoke` | Owner or explicit grant administrator; body exactly `{}`; 200 `{grant}`; wrong patient/grant/owner 404 |
| GET `/patients/{patient_id}/assessments` | Existing owner access, or doctor with valid grant; existing pagination/response unchanged |
| GET `/patients/{patient_id}/assessments/{assessment_id}` | Existing owner access, or doctor with valid grant; nested assessment must belong to permitted patient |

Existing profile reads, profile creation and assessment creation remain patient-only.
Admin accounts, including grant administrators, cannot read assessment history or
details. Doctor role alone grants no access. Review-write blockers and all existing
review endpoints' absence remain unchanged. Bearer authentication, JSON errors and
Cache-Control no-store are reused. Frontend route guards are unchanged; there is no
new doctor workspace or grant-management screen.

Deployment instructions (not executed against the running database): configure the
intended database through the existing mechanism, then:

```powershell
.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe -B -m flask --app backend.app authorize-grant-administrator --email <existing-admin-email>
```

Restart that configured backend after migration using its established launcher.
The local launcher still upgrades its selected local database when explicitly
invoked; it was not restarted here. No live admin permission or grant was created.
Downgrading 0005 destroys grant/permission history and is intended only for reviewed
maintenance or disposable tests, never an automatic rollback strategy.

## Executed verification

From workspace root:

| Exact command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_access_grants.py' -v` | 16 passed; OK; exit 0; 8.876 seconds |
| `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v` | 113 passed; OK; exit 0; 52.012 seconds |
| `.venv/Scripts/python.exe -B -m pip check` | Exit 0; No broken requirements found |
| `.venv/Scripts/python.exe -B -m flask --app backend.app routes` | Exit 0; 13 route operations; no clinical review/prediction route |

From `frontend`:

| Exact command | Result |
| --- | --- |
| `npm test` | 36 passed, 0 failed/skipped; exit 0; 14.648 seconds |
| `npm run build` | Exit 0; 35 modules; 1.31 seconds; unchanged asset names |

Focused tests exercised real migrated SQLite persistence and Flask routes, including
expiry at the exact boundary on both read routes, revocation with the existing
JWT, owner/admin revocation, unauthorized administration, cross-patient and
cross-doctor isolation, nested assessment IDs, server-field injection, missing or
malformed references, renewal/history, ORM mutation denial, tampered-duration
rejection, schema agreement, downgrade/reupgrade preserving assessments and
generated MySQL migration SQL. The first focused command also discovered 24
imported patient tests (40 passes); switching to a module import made focused
discovery correctly contain only this milestone's cases.

`test_real_http_login_grant_read_and_revoke_on_disposable_server` started a real
Werkzeug HTTP server on an ephemeral loopback port with a migrated disposable
SQLite database and synthetic accounts. Real urllib requests verified login,
doctor 403 before issuance, owner assessment creation, authorized issuance 201,
doctor history/detail 200, admin clinical denial, owner revocation 200 and doctor
history/detail 403 afterward. The server was shut down in test cleanup. Existing
frontend integration tests separately exercised their real Flask/Vite proxy servers.
This evidence is actual execution, not a mocked grant success.

Receptionist remains absent from ROLE_CODES/schema/provisioning. The focused test
verifies database rejection of that unsupported role and that an injected JWT role
claim cannot grant clinical access. A real receptionist-account acceptance test
cannot run until a separately authorized role migration exists; no four-role
provisioning claim is made.

No running application database migration, live MySQL verification, browser
interaction, production data modification or frontend port change occurred. No
running server was restarted. Only isolated SQLite and ephemeral HTTP servers were
used for new grant behavior. External consent-document authenticity was not tested.
Deployment and browser integration remain unverified; policy is settled for this
backend slice. V17 artifacts, training/source/dataset, preprocessing/output contract,
loading controls, watchdog, Docker/WSL, dependencies and environment configuration
were not changed.

## Files

Created: `backend/app/models/access_grant.py`,
`backend/migrations/versions/0005_patient_doctor_grants.py`,
`backend/app/auth/grants.py`, `backend/app/api/access_grants.py`,
`tests/backend/test_access_grants.py`, this report.

Modified: `backend/app/models/__init__.py` (model registration),
`backend/app/auth/__init__.py` (explicit operator authorization command),
`backend/app/api/__init__.py` (grant route registration),
`backend/app/api/patients.py` (only the two assessment-read permissions),
`tests/backend/test_foundation.py` (route inventory),
`docs/architecture/ayursage-system-map.md` and
`docs/setup/implementation-checklist.md` (current slice status).

No Git diff/commit claim: this workspace is not a Git repository.

## Acceptance preflight — 14 October 2026 (Asia/Calcutta)

**Stopped before migration: target/authorization require confirmation.** Read the
report, migration 0005 and all preceding migrations, standard database configuration,
Alembic environment/configuration, local launcher and VS Code startup tasks. No
application code, dependency, environment, database, process or frontend port changed.

Read-only commands and observed results:

| Check | Actual result |
| --- | --- |
| `.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini heads` | One head: `0005_patient_doctor_grants`; exit 0 |
| `.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini history` | Linear 0001 → 0002 → 0003 → 0004 → 0005; exit 0 |
| `Get-NetTCPConnection -State Listen` filtered to 5000/5173/5174, and `Get-CimInstance Win32_Process` | Both frontend ports listening; 5173 PID 27788 belongs to this workspace. Port 5000 reported PID 11656, a standard `-m flask --app backend.app run` child of project-venv PID 27544. Older local launcher PID 26200/parent 7048 also remains running |
| `netstat -ano -p tcp` filtered to `:5000` | **Two simultaneous LISTENING rows on 127.0.0.1:5000**, PIDs 11656 and 26200; the single CIM listener result did not show this ambiguity |
| Read-only process environment inspection using OpenProcess query/read access and ReadProcessMemory; case-insensitive names | Standard Flask PID 11656 has neither DATABASE_URL nor JWT_SECRET_KEY. Local launcher PID 26200 also has neither in its environment, but its inspected source supplies explicit SQLite/key configuration. No credential/secret values were printed |
| Python sqlite3 connection to `.local/auth/auth.sqlite3` with URI `mode=ro` and `PRAGMA query_only=ON` | Local candidate revision `0004_assessment_reviews`; 7 users, 7 patients, 3 assessments; grant tables absent. This is persistent local development data, **not a disposable test database** |
| Python urllib GET `/api/health` and `/api/auth/me` at direct 5000 and through both localhost frontend ports | Each health 200 JSON; each anonymous `/me` 401 JSON. These requests alone cannot identify which overlapping backend listener served them |
| `cua.getState()` | `apps: []`, `browsers: []`; browser interactions unavailable |

The local launcher's configured backend is SQLite at this workspace's
`.local/auth/auth.sqlite3`. The standard Flask process has no configured database
according to its environment and the inspected environment-only factory. A fresh
standard unconfigured factory would return authentication 503, while observed
requests returned 401. Combined with the duplicate netstat listeners, this prevents
attributing the frontend's live requests to one authoritative backend/database.
No active MySQL target was established. The local SQLite file is a verified
candidate, not an assumed definitive HTTP acceptance target.

Before/after revision for the local candidate: **0004 / 0004 (unchanged)**.
Revision of an authoritative running HTTP database: unresolved. Backup: **not
created or verified**, because no target was selected for modification. Migration:
**not applied**. No synthetic accounts, administrator permission, grants or
assessments were created in this preflight. Grant persistence/expiry/revocation/
isolation and authenticated patient acceptance checks against the actual target
remain pending. Prior automated/disposable results above remain historical; suites
were not rerun because no implementation change was made and the user required
stopping when the target or modification authorization is ambiguous.

Confirmation needed: select `.local/auth/auth.sqlite3` as the intended persistent
development target (or identify another exact target/environment); explicitly
authorize its verified backup, 0005 upgrade, synthetic acceptance records and
resolution of the duplicate project-owned Flask listeners. No shared/production
target, resetting data, other-project process operation or port change is implied.
After confirmation, backup must be verified before migration, and database/HTTP
checks and regressions must run against the selected target. Browser acceptance
still requires available browser tooling.

## Authorized development acceptance completed — 14 October 2026

The user explicitly selected `.local/auth/auth.sqlite3` and authorized a verified
backup, duplicate-listener resolution, migration 0005 and synthetic acceptance.
The checks below supersede the blocked preflight for this **local development
SQLite** target. No production/shared target or live MySQL was selected or modified.

### Process identification and backup (before stopping any process)

Read the report, migration instructions, standard config, Alembic env and 0005.
Read-only CIM and process-memory inspection established:

| Purpose | Listener / parent PIDs | Executable and command | Working directory/configuration |
| --- | --- | --- | --- |
| Intended local development launcher | 26200 / 7048 | Listener: base Python312 `python.exe`; parent: project `.venv/Scripts/python.exe`; `-B -u -m backend.local --port 5000` | Both inspected listener working directories equal `C:\Users\yvasa\Videos\PROJECT-Ayursage`. Launcher source selects `.local/auth/auth.sqlite3` and reads existing `.local/auth/jwt.key`; absence of environment DATABASE_URL/JWT_SECRET_KEY is expected for this explicit launcher |
| Redundant unconfigured Flask | 11656 / 27544 | Listener: base Python312 `python.exe`; parent: project `.venv/Scripts/python.exe`; `-m flask --app backend.app run` | Same verified workspace; DATABASE_URL and JWT_SECRET_KEY absent; standard factory provides neither fallback |

`netstat -ano -p tcp` confirmed both LISTENING on 127.0.0.1:5000. Command/parent
identities were rechecked immediately before termination. No unrelated process
was stopped. Read-only inspection used OpenProcess query/read permissions only;
no secrets, credentials or unrelated environment values were printed or recorded.

Consistent backup created with Python sqlite3 `Connection.backup`, not a filesystem
copy of a live database:

`C:\Users\yvasa\Videos\PROJECT-Ayursage\.local\backups\auth-before-0005-20261014-000705.sqlite3`

The backup opened read-only with `PRAGMA integrity_check = ok`. Source and backup
both had revision `0004_assessment_reviews`, 7 users, 7 patients, 3 assessments,
0 review rows and 3 roles. All original table row hashes matched, and the source
snapshot was unchanged before/after backup. Evidence:
`.local/acceptance/backup-evidence.json`. Original and backup remain preserved.
The first backup helper invocation stopped before backup creation because Windows
had no `tzdata` for ZoneInfo; standard-library fixed UTC+05:30 timestamping resolved
that helper startup issue without dependencies. The actual backup verification
passed before any listener termination or migration.

### Listener resolution, migration and reload

Stopped only redundant listener 11656, after matching its command and project-venv
parent 27544. Port 5000 then had one listener, intended PID 26200; HTTP health 200.
Reconfirmed the approved absolute target, revision 0004, original row hashes and
verified backup before applying any migration. ScriptDirectory confirmed a single
head 0005 and its 0004 predecessor. Used existing Alembic supplied-connection
workflow (`Config`, SQLAlchemy `engine.begin`, `config.attributes['connection']`,
`command.upgrade(config, '0005_patient_doctor_grants')`), exactly as supported by
the existing migration environment. No DATABASE_URL/environment edits were needed.

Revision **0004_assessment_reviews → 0005_patient_doctor_grants**; integrity and
foreign-key checks passed. Original users/patients/assessments/reviews/roles matched
the backup byte-for-byte at the row-value level. Counts remained 7/7/3/0/3 before
synthetic testing. Evidence: `.local/acceptance/migration-evidence.json`.

After successful explicit migration, rechecked and stopped intended old listener
26200 to reload current code, then started the same launcher with hidden-window
Start-Process, project working directory and local log redirection. Its existing
startup upgrade was an idempotent no-op at head. Final launcher parent PID **22568**,
sole listener PID **21836**, both `python.exe`, command
`-B -u -m backend.local --port 5000`. `netstat` confirmed exactly one LISTENING row.
Logs are `.local/acceptance/backend.stdout.log` and `backend.stderr.log`.
Existing frontend listeners **5173/PID 27788** and **5174/PID 20844** were untouched
and unchanged at final verification; acceptance requests used localhost:5173.

### Actual target database and live HTTP checks

`.local/acceptance/live_grants.py` generated credentials only in memory and used
real HTTP through `http://localhost:5173/api` to the intended Flask listener and
the migrated persistent database. Synthetic staff were provisioned with the
existing Flask CLI commands via its CLI runner, using the same explicit local
database/key config; no alternative staff-provisioning code was introduced.
Only synthetic admin 11 received grant-administration permission. A synthetic
consent evidence file ties patient owner, doctor, administrator and fixed scope to
the two references: `.local/acceptance/synthetic-consent-178834b3975b.txt`.

| Real HTTP operation | Observed status/result |
| --- | --- |
| Register two synthetic patients | 201 each; login, `/auth/me`, own profile 200 |
| Save all 12 assessment inputs; history/detail; fresh-client login/retrieval | 201 save; 200 history/detail and persisted account/assessment retrieval |
| Doctor history before grant; admin issuance before explicit permission | 403 / 403 |
| Grant without consent reference | 400 |
| Authorized admin issuance with consent reference | 201; persisted issuer, owner link, reference, issuance/expiry and scope confirmed by read-only SQL |
| Granted doctor's history/detail | 200 / 200; exact saved assessment roundtrip |
| Same doctor reads other synthetic patient's history/detail | 403 / 403 |
| Doctor patient-profile reads and assessment write | 403; POST did not create another assessment |
| Admin clinical history read | 403 despite grant-administration permission |
| Attempted review action | 404; no review endpoint enabled |
| Patient attempts issuance; other owner attempts revocation | 403 / 404 |
| Owner lists grants, then revokes grant 1 | 200 / 200; next doctor history/detail requests 403 / 403 using the same JWT |
| Admin issues replacement grant 2 with new reference, then revokes it | 201; doctor detail 200 before revocation; revocation 200; next doctor detail 403 |
| Owning patient's detail after revocation | 200 |
| Missing bearer; invalid credentials | 401 / 401 |

Read-only SQL independently confirmed issuer/consent/issuance/expiry persistence.
Expiry minus issuance is exactly **2,592,000 seconds (30 days)** under the existing
UTC convention. Boundary enforcement against the **actual migrated database** was
checked separately using Flask test-client GETs with only the verification
process's `auth.grants.utc_now` controlled: both history/detail returned 200 at
expiry minus one second and 403 at exact expiry. The running server clock and
database timestamps were never changed. This is an actual-database controlled-clock
check, **not a network HTTP request after waiting 30 days**. Ordinary live HTTP
still returned 200 before revocation afterward, confirming that boundary checks
did not alter the grant. Original review-write guards also passed full regressions.

Safe evidence: `.local/acceptance/live-evidence.json` contains method/path/status,
synthetic IDs, controlled-clock observations and counts, without passwords/JWTs.
Synthetic users: owner 8, other patient 9, doctor 10, admin 11; patients 8/9;
assessment 4; grants 1/2. Both grants are revoked with persisted revoker/time
(owner 8 and admin 11 respectively). No supported deletion endpoint exists;
synthetic accounts/assessment and protected grant history are retained instead of
using destructive raw SQL cleanup. No existing record was deleted/changed.
Final counts: 11 users, 9 patients, 4 assessments, 0 reviews, 3 roles, 2 revoked
grants and 1 synthetic grant-administrator permission. Generated credentials were
not saved. Final source/backup integrity checks both passed; foreign_key_check was
empty; each original backup row still exactly matched its source row.

### Exact commands and results

All final commands below exited **0**. Helpers are retained verification artifacts
under `.local/acceptance`, not application code or configuration changes.

| Working directory / command | Actual result |
| --- | --- |
| Root: `.venv/Scripts/python.exe -B .local/acceptance/inspect_processes.py` | Both listener working directories and configuration presence verified read-only |
| Root: `.venv/Scripts/python.exe -B .local/acceptance/backup.py` | Consistent persistent backup, revision/count/hash agreement, integrity ok |
| Root: `.venv/Scripts/python.exe -B .local/acceptance/migrate.py` | Existing Alembic workflow: exact target 0004 → 0005; original records unchanged |
| Root: `.venv/Scripts/python.exe -B -u -m backend.local --port 5000` via hidden-window Start-Process | Sole intended listener 21836, parent 22568; persistent database/key reused |
| Root: `.venv/Scripts/python.exe -B .local/acceptance/live_grants.py` | Live HTTP and target SQLite assertions PASS; both grants revoked |
| Root: `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_access_grants.py' -v` | 16 passed; 7.288 seconds; includes real disposable SQLite HTTP verification |
| Root: `.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v` | 113 passed; 45.775 seconds |
| Frontend: `npm test` | 36 passed, 0 failed/skipped; 13.821 seconds; isolated real Flask/Vite contracts |
| Frontend: `npm run build` | Passed; 35 modules; 1.52 seconds |
| Root: `.venv/Scripts/python.exe -B -m pip check` | No broken requirements found |

Process operations were exact revalidated PID operations: `Stop-Process -Id 11656`
and, after migration, `Stop-Process -Id 26200`. Final listener verification used
`netstat -ano -p tcp` and `Get-NetTCPConnection -State Listen`. No blanket process
termination, shell environment edit, database reset or overwrite was performed.

Browser verification: `cua.getState()` returned `apps: []`, `browsers: []`; no
browser was operated. Therefore this accepts the authorized local SQLite/database
and HTTP slice, **not mounted-browser acceptance or live MySQL compatibility**.
Automated tests, disposable real HTTP tests, persistent target checks and
controlled-clock checks are distinguished above. Application code/policy, frontend
ports, dependencies, V17, Docker/WSL and review-write blockers were unchanged.
