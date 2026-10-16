# Administrator grant-management UI

16 October 2026. Small application milestone following verified doctor clinical
review. It completes an existing Flask issue/list/revoke workflow; no backend,
migration, staff-provisioning or authorization policy was added or changed.

## Operator workflow

Sign in as an existing administrator and choose Manage patient–doctor grants,
or open `#/admin/grants`. Administrator role alone is insufficient: the existing
trusted CLI provisioning of GrantAdministrator remains a backend prerequisite.
An unprovisioned administrator receives 403 and no issue form after lookup.

Enter a verified patient profile ID and load their grants. This uses only
GET /api/patients/{id}/doctor-access-grants. No patient discovery endpoint,
profile read, clinical content or additional administrative bypass was introduced.
The list reuses the existing patient grant renderer with administrator wording,
bounded pagination, permission labels and confirmation before revocation.

To issue, enter a verified doctor account ID and the bounded opaque reference
to retained consent. Read-only access is the default. Explicitly selecting
clinical-review permission requires consent covering doctor-authored review and
manual prescription recording. Confirm the consent attestation, then inspect the
confirmation showing selected patient, doctor, reference and permissions. Only
Confirm issue grant sends a POST. The server remains responsible for verifying
administrator permission, patient/doctor links, exact duration, consent format,
active/reused-consent conflicts and the actual saved record.

Changing doctor/reference/permissions invalidates the consent checkbox. Loading
another patient or completing a mutation resets the draft. Cancelling confirmation
for the same patient retains the draft and does not send a write. Successful issue
or revoke displays only the server-returned grant, with an explicit prompt to
refresh full history; it does not pretend that this is the complete historical list.
Errors clear old grant rows/confirmations and retain a refresh action. Duplicate
submissions are suppressed; unmounted requests cannot repopulate state. A lost or
invalid response is not evidence that a grant was not created: refresh before
attempting issuance again. No automatic issuance retry occurs.

The server still rejects custom scope, expiry, issuer/owner injection and role-only
clinical access. Patients retain their existing viewing/revocation workflow;
appointments do not grant access. No new staff-role management, account search,
patient-consent document storage or clinical-data release is implemented.

## Actual verification

Newly executed for this UI:

- 42 frontend state/service/route tests passed: 7 new administrator tests plus
  existing patient, doctor and foundation regressions.
- 3 new administrator rendering tests and 13 existing patient rendering tests
  passed individually after the final UI change.
- Existing backend AccessGrantTests: 16 passed on disposable SQLite/isolated HTTP.
- Production build write:false passed with 43 modules; dist was not written.
- Real installed Chrome 155.0.8059.40, existing playwright-core, disposable
  in-memory SQLite/Flask at migration head 0007: 4 browser stages passed
  (Node reports 5 tests including parent), 7.218s, no skips.

Browser stages: authorized admin loads nonclinical grant metadata and revokes an
existing grant; issues a read-only grant and reloads/re-authenticates to retrieve
it; explicitly opts into review permission, cancels confirmation without a POST,
reconfirms/issues and revokes; unprovisioned admin receives actual backend 403,
while a patient cannot enter the admin route. Final doctor directory excludes the
revoked patient. Authentication/authorization and HTTP responses were not mocked.

The first browser run reproduced a form draft-reset bug: clearing an old success
notice during preparation erased the draft behind the confirmation, so cancel and
reconfirm could not submit. The narrow fix resets on patient changes and nonempty
success notices only. The same browser scenario passed after the fix.

One final combined Vite rendering run failed/stalled during initialization and its
exact owned Node process was stopped. The cause was not conclusively established.
Both files then passed independently; this is not a claim that the combined-run
issue was fixed. No unrelated process was stopped.

No MySQL or clinical-review acceptance scenario was rerun for this milestone;
their prior results remain separate. The 127/80 counts in clinical-review evidence
are historical for this follow-up. No model, observer or security-policy work ran.

Commands (frontend/):

```powershell
node --test --test-isolation=none tests/admin-grants.test.js tests/patient.test.js tests/doctor.test.js tests/foundation.test.js
node --test --test-isolation=none tests/admin-grants-render.test.js
node --test --test-isolation=none tests/patient-render.test.js
node --input-type=module -e "import { build } from 'vite'; await build({ build: { write: false } });"
$env:AYURSAGE_E2E_DATABASE = 'sqlite'
$env:AYURSAGE_E2E_ADMIN_GRANTS = '1'
$env:AYURSAGE_PLAYWRIGHT_MODULE = 'C:\Users\yvasa\Videos\AYURSAGE\.phase9-release\frontend\node_modules\playwright-core\index.mjs'
node --test --test-isolation=none tests/e2e/doctor-access.test.js
```

Backend command (repository root):

```powershell
@'
import sys,unittest
sys.path.insert(0,'tests/backend')
r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName('test_access_grants.AccessGrantTests'))
raise SystemExit(not r.wasSuccessful())
'@ | .venv/Scripts/python.exe -B -
```

Existing E2E modes remain unchanged unless the new administrator flag is set.
The administrator and clinical-review modes are mutually exclusive. Fixture-only
unprivileged administrator provisioning permits real backend-denial checks and
does not add an application route or authentication bypass. Browser, Vite and
backend processes are closed at teardown; SQLite is in memory. No existing database
was accessed/migrated, package installed, port configuration changed or service
launched persistently.

## Files for this slice

New: frontend/src/admin/grants.js, frontend/src/pages/AdminGrantsPage.jsx,
frontend/tests/admin-grants.test.js, frontend/tests/admin-grants-render.test.js,
this document.

Updated: frontend/src/services/patients.js, frontend/src/pages/PatientProfilePage.jsx,
frontend/src/pages/HomePage.jsx, frontend/src/routing/routes.js,
frontend/src/routing/Router.jsx, frontend/tests/e2e/doctor-access.test.js,
frontend/tests/flask_auth_fixture.py, docs/architecture/ayursage-system-map.md.

V17 provenance/runtime, observer/security acceptance and prediction parity remain
blocked. Human review does not imply approved model inference or patient release.
