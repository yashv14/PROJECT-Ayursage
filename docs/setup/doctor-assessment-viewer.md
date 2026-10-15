# Doctor assessment viewer

MySQL follow-up: [disposable MySQL verification](mysql-access-verification.md)
records the actual MySQL 8.0.46/browser pass, seven database checks and minimal
singleton-key compatibility fix. It supersedes the MySQL-unverified limitation
of the historical milestones below for this local workflow only.

## Real-browser access workflow verification — 15 October 2026

The browser limitation in the earlier milestone records below is now superseded
for this local SQLite scenario only. `frontend/tests/e2e/doctor-access.test.js`
passed using existing playwright-core 1.56.0 and installed Google Chrome
155.0.8059.40, headlessly. No browser/package download or installation occurred.
The connected-browser inventory was empty; a Playwright cache link located the
existing runner in the older checkout. Its cached headless-shell directory was
incomplete, so the test explicitly uses an already-installed Chrome/Edge channel.

The test extends `frontend/tests/flask_auth_fixture.py` with an opt-in
`--doctor-access-fixtures` mode. It uses existing account helpers, migrations only
against sqlite:///:memory:, the trusted grant-administrator CLI and real admin
grant-issuance HTTP API. A synthetic assessment is saved explicitly without
prediction. Test-only guards reject V17 load/predict calls. No new API/test bypass,
application change, persistent database, real patient record or user browser
profile is used. Loopback backend/Vite ports are ephemeral; browser contexts are
isolated and browser-context traffic outside the test origin is blocked. Teardown
closes browser/Vite and waits for the owned base-Python fixture process to exit.

Actual browser workflow:

1. Patient logs in and sees the issued grant on My Profile.
2. Doctor logs in, sees only the authorized patient in the directory, selects that
   patient/history/assessment and reads eight synthetic categorical values, four
   explicit numeric zeroes, patient notes and the stored timestamp.
3. Another doctor sees an empty directory and a denied direct assessment link.
   Patient and receptionist UI role guards reject doctor pages. Real HTTP requests
   also reject other-doctor/admin/receptionist clinical reads, unrelated patient
   reads and non-doctor directory requests.
4. Patient confirms revocation through My Profile. The doctor explicitly refreshes
   the assessment: the test observes the new real GET return 403, then asserts
   notes/input details are absent. Returning to the directory excludes the patient;
   additional real HTTP history/detail requests are denied.

No instantaneous remote removal of already displayed information is claimed.
Revocation is verified on the next request and UI handling of that denial.

Run from `frontend` with an existing installed runner (no automatic acquisition):

```powershell
$env:AYURSAGE_PLAYWRIGHT_MODULE = 'C:\Users\yvasa\Videos\AYURSAGE\.phase9-release\frontend\node_modules\playwright-core\index.mjs'
node --test --test-isolation=none tests/e2e/doctor-access.test.js
```

The module location above is the runner actually used, not a repository dependency
or portable path. Supply another existing playwright-core index.mjs when needed.
AYURSAGE_BROWSER_CHANNEL optionally selects installed chrome (default) or msedge;
AYURSAGE_TEST_PYTHON optionally selects an existing Python environment. Missing
tooling fails explicitly; nothing is installed or silently skipped. The nested
E2E file is opt-in and is not selected by the current tests/*.test.js npm script.
Windows runs required subprocess access outside the sandbox. An initial launch
failed on the incomplete shell cache; a subsequent test-harness-only optimization
override prevented React client loading. The override was removed; final browser
checks passed without modifying application code.

Verification levels actually run in this task:

| Level | Current result |
| --- | --- |
| Frontend unit/state | 49 passed: doctor, patient, foundation, session, assessment-prediction files |
| Frontend server rendering | 18 passed: doctor-render (5), patient-render (13); synthetic fixtures |
| Backend authorization | 24 passed: AccessGrantTests (16), DoctorDirectoryTests (8), real Flask/JWT/SQLAlchemy over disposable SQLite; includes disposable HTTP test |
| Browser E2E | One real-browser scenario, four passing stages; Node reports 5 passing tests including parent |
| Production build | Passed with write:false; existing dist not overwritten |
| Live MySQL/deployed environment | Not performed; no claim of deployed or MySQL acceptance |

Exact regression commands from frontend:

```powershell
node --test --test-isolation=none tests/doctor.test.js tests/patient.test.js tests/foundation.test.js tests/session.test.js tests/assessment-prediction.test.js
node --test --test-isolation=none tests/doctor-render.test.js
node --test --test-isolation=none tests/patient-render.test.js
node --input-type=module -e "import { build } from 'vite'; await build({ build: { write: false } });"
```

Backend command from workspace root:

```powershell
@'
import sys, unittest
sys.path.insert(0, 'tests/backend')
import test_access_grants, test_doctor_directory
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (test_access_grants.AccessGrantTests, test_doctor_directory.DoctorDirectoryTests))
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
'@ | .venv/Scripts/python.exe -B -
```

All final commands exited 0; no existing regression or application defect was
identified. Browser expiry timing, pagination and deployed/MySQL behavior were not
exercised in this single scenario (expiry/pagination have API/state coverage).
Portable repository/CI browser-runner provisioning remains a separately approved
tooling task; this test deliberately reuses the installed external runner.

## Authorized-patient directory extension — 15 October 2026

Doctor home now opens a directory at `#/doctor/assessments`, replacing the manual
ID form. Each patient link opens the existing grant-protected assessment viewer.
Direct history/detail links remain supported and independently authorized.

`GET /api/patients/authorized?after_id=0` requires a validated doctor JWT and
returns only `{"patients":[{"id":1}],"next_after_id":null}`. IDs are illustrative;
no patient names, emails, owner IDs, consent references or grant metadata are
returned. The existing Patient model has no name/display field. Pagination is
ascending by patient ID, at most 20 entries, with a last-ID cursor when another
page exists. Only one bounded integer `after_id` is accepted; caller-supplied
doctor IDs, unknown parameters and repeated cursors are rejected with 400.
Responses use the existing no-store policy and generic authentication/DB errors.

`auth/grants.py:assessment_read_grants` and `valid_grant_details` are shared by
directory and assessment authorization. They derive doctor identity from
`g.current_user`, require patient/consent-owner linkage, assessment_read scope,
issued status, active slot, no revocation, issued_at <= UTC now < expires_at,
exactly 30-day duration and a nonblank consent reference. Scalar queries re-read
state rather than trusting ORM identity-map objects. Directory reads stream batches
of 20 grant rows and retain at most 21 distinct authorized patient IDs; exact
duration/whitespace checks retain Python semantics on SQLite/MySQL. No appointment
assignment, doctor role alone, client parameter or earlier response grants access.

Refresh, navigation and tab return fetch new directory data. Each next page replaces
the previous page instead of retaining previously authorized IDs whose grants may
have changed. Refresh returns to page one. Loading/errors clear displayed IDs;
pending duplicates and late hidden/unmounted responses are suppressed. The existing
viewer independently rechecks access when a patient or assessment is opened.
There is no real-time revocation notification; changes are detected on requests.

Verification for this extension: 8 focused directory backend tests plus 53 existing
grant/patient/foundation backend regressions passed (61 distinct tests). These use
real Flask/JWT/SQLAlchemy against migrated disposable in-memory SQLite, never the
local application database. The existing disposable HTTP-server test was excluded.
MySQL query compilation passed; no live MySQL verification is claimed.

Frontend verification: 49 service/state tests, 5 doctor render tests and 13 patient
render tests passed (67 distinct tests). The in-memory production build passed with
write:false. Frontend requests are mocked and rendering is server-side; live browser
and deployed-backend integration remain unverified. The first new revocation test
failed because issuance/revocation fixture clocks differed; both fixture clocks now
use the controlled instant, and all final checks above passed.

No migration, dependency, V17 artifact/source/loading-policy or clinical-write
change was made. Existing patient grant management, assessment reads and read-only
doctor viewer remain in place. The original viewer milestone below is historical;
its missing-directory/manual-entry limitation is superseded by this extension.

## Original viewer milestone (historical)

Implemented 15 October 2026 (Asia/Calcutta). Frontend-only read access using the
existing Flask grant-protected endpoints. No backend, schema, migration,
dependency, V17, loading-policy or clinical-write change.

## Navigation and available data

Doctor home links to `#/doctor/assessments`. Enter a known patient ID to open
`#/doctor/patients/{patient_id}/assessments`; select a record to open
`#/doctor/patients/{patient_id}/assessments/{assessment_id}`.
All viewer routes require a signed-in doctor. Patient, administrator and
receptionist routes retain their existing permissions.

There is no doctor-accessible patient directory, patient name lookup or grant
directory endpoint. The viewer therefore requires an ID supplied outside this
screen; it neither enumerates patients nor treats knowledge of an ID as access.
Only a successful assessment response supplies displayed clinical data.

Existing authenticated GET contracts:

- `/api/patients/{patient_id}/assessments?limit=20&after_id={cursor}` returns
  `{assessments, next_after_id}`.
- `/api/patients/{patient_id}/assessments/{assessment_id}` returns `{assessment}`.
- Each assessment exposes `id`, `patient_id`, `recorded_by_user_id`, `created_at`,
  `inputs` and `notes`. Legacy `inputs:null` remains absent input data.

The existing patient service validates responses and patient/assessment links.
The viewer reuses the history/detail screens in read-only mode, showing stored
inputs, patient-supplied notes, IDs and server timestamps without inventing a
timezone. No prediction/approval/prescription/care-note editing is added.

## Access and stale-response handling

Flask remains the authorization authority and checks grant scope, owner linkage,
expiry and revocation on each GET. The viewer performs no profile, grant or write
requests. Existing bearer authentication and 401 session handling are reused.

Navigation and refresh make fresh requests. Loading clears visible clinical data,
including during pagination; failed requests retain no old rows/detail/cursor.
Successful load-more appends the captured prior page only after the new response
passes the service's validation. Repeated requests are suppressed while pending;
superseded and unmounted responses cannot repopulate state. Hiding the tab clears
the viewer, and returning/focusing revalidates. Returning from detail starts a
fresh history request rather than restoring a cached authorization decision.

The backend supplies no real-time grant-revocation notification. Already delivered
data cannot be recalled; remote revocation is detected on the next request, not
claimed to be detected instantaneously. Denied requests clear displayed records.

## Verification actually executed

From `frontend`, all commands exited 0:

```powershell
node --test --test-isolation=none tests/doctor.test.js tests/patient.test.js tests/foundation.test.js tests/session.test.js tests/assessment-prediction.test.js
node --test --test-isolation=none tests/doctor-render.test.js
node --test --test-isolation=none tests/patient-render.test.js
node --test --test-isolation=none tests/render.test.js
node --test --test-isolation=none tests/reception.test.js
node --input-type=module -e "import { build } from 'vite'; await build({ build: { write: false } });"
```

Results: 45 service/state tests and 21 render/regression tests passed (66 distinct
tests, including 11 new doctor tests). In-memory production build passed; existing
dist output was not overwritten. Render/build commands used subprocess access
outside the sandbox for Vite's Windows helper. An initial combined render run
passed assertions but logged a Vite dependency-cache rename warning; separate
suite runs above passed without that warning.

These are synthetic frontend/mock and server-rendering checks. No live browser,
backend, MySQL, real patient data, model, migration or clinical operation was
executed. Live synthetic-account grant/expiry/revocation and browser navigation
verification remain outstanding; these tests do not establish backend security.
