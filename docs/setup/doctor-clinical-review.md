# Doctor clinical review

## Disposable MySQL/browser verification — 16 October 2026

**PASS for this local synthetic workflow.** This section supersedes the browser
and live-MySQL limitations in the implementation record below only for the tested
cases. No application defect was found and no application or migration code was
changed during this verification. Earlier results remain historical; the results
in this section were newly executed.

### Target and migration evidence

The existing owned-instance helper provisioned MySQL **8.0.46**, schema
`ayursage_e2e_daff9ddcd42a`, loopback port **54695**, server UUID
`cca18129-c914-11f1-aae8-00155d03dd51`, in the new
`.local/mysql-e2e-daff9ddcd42a/data` directory. Before schema writes, the helper
checked the owned process PID, datadir and port. Before migration writes, the
application checked schema, datadir, port, server UUID, dialect and an empty schema.
It did not use DATABASE_URL or connect to an existing application database.

Migrations applied through **0006_receptionist_appointments**. Synthetic legacy
users, patient, assessment, one read-only grant and one explicitly synthetic legacy
review were then committed using that actual schema. Upgrade to
**0007_clinical_review** passed. Assertions confirmed that the old grant's
allow_review defaulted to false and the old review retained its sequence, states
and reason, with null recommendations/prescriptions. The application reported
MySQL and head 0007. No MySQL downgrade was attempted.

### Real database and browser evidence

Three concurrency trials used different synthetic assessments and two independent
MySQL connections per trial. A third connection temporarily held the assessment
row lock. SQL instrumentation observed both review requests entering their actual
grant-lock statements before releasing the blocker; it did not mock queries,
authorization or results. The concurrent requests went through Flask test clients
in separate threads, not a threaded HTTP server. All three returned **one 201 and
one 409**. GET confirmed exactly one initial event and the winning content.

| Trial | Assessment | Responses | Distinct request connections | Both lock requests observed | Final version after revisions |
| --- | ---: | --- | ---: | --- | ---: |
| 1 | 24 | 201 / 409 | 2 | true | 3 |
| 2 | 25 | 201 / 409 | 2 | true | 3 |
| 3 | 26 | 201 / 409 | 2 | true | 3 |

Each trial additionally verified stale-version denial, returned -> pending ->
approved append history, unchanged original event, doctor identity, Z-suffixed UTC
timestamps, terminal-decision denial, ORM history-edit denial and revoked access.
Seven review-check groups and seven existing MySQL access/persistence regression
groups passed. These do not establish arbitrary-load performance or exhaustive
revocation/concurrency interleavings.

The existing playwright-core **1.56.0** installation and installed Chrome
**155.0.8059.40** exercised actual React/Vite, Flask, JWT authentication and this
MySQL instance. Only synthetic records were used. No authorization or HTTP response
was mocked. The seven browser/HTTP stages passed:

1. Patient logs in and sees the issued grant on My Profile.
2. Doctor selects the authorized patient, assessment history and stored detail.
3. Other doctor/roles and unrelated patients remain excluded or denied.
4. Read-only grant denies review POST (403), shows no save form; unrelated doctor,
   patient, administrator and receptionist review GET/POST are denied.
5. Patient revokes the read-only grant through the API; authorized admin issues a
   new consent-attested review-enabled grant. Doctor fills clinical notes, all four
   manual recommendations and all prescription fields, then saves returned_for_changes
   through the UI. Actual POST returns 201 with exact persisted content and author.
6. Full page reload and fresh login retrieve the saved history and form content.
   Doctor revises notes/recommendation, resubmits, then approves through the UI.
   Three ordered events persist; first event is unchanged; approved record has no
   save form. Stale and terminal API submissions return 409.
7. Patient revokes the review-enabled grant through My Profile. A new doctor GET
   returns 403, clears clinical detail/review content, and directory excludes the
   patient. Subsequent review GET/POST also return 403. No instantaneous removal
   from an open remote tab is claimed.

Node reported **8 tests passed** (seven stages plus parent), no failures/skips,
22.533 seconds. Existing access E2E mode remains the default; the additional review
checks are enabled only with AYURSAGE_E2E_CLINICAL_REVIEW=1 and require MySQL.

### Newly executed regressions and build

| Check | Result |
| --- | --- |
| Affected backend tests listed below | **127 passed**, 15.522s; disposable SQLite, not 127 MySQL tests |
| Frontend service/state tests | **55 passed** |
| Review/doctor/patient/reception render regressions | **4 + 5 + 13 + 3 passed** |
| Frontend total excluding browser | **80 passed** |
| Production build, write:false | **PASS**, 41 modules, 246ms; dist not written |
| E2E JavaScript syntax check | PASS |

No code failure was encountered and no defect fix was needed. No tools/packages
were installed. V17 load/predict guards remained active in the disposable backend;
assessments were saved with predict:false. Existing mocked prediction-contract
tests remain transport/state evidence only, never real-inference validation.

### Reproduction and cleanup

From frontend/:

```powershell
$env:AYURSAGE_E2E_DATABASE = 'mysql'
$env:AYURSAGE_E2E_CLINICAL_REVIEW = '1'
$env:AYURSAGE_PLAYWRIGHT_MODULE = 'C:\Users\yvasa\Videos\AYURSAGE\.phase9-release\frontend\node_modules\playwright-core\index.mjs'
node --test --test-isolation=none tests/e2e/doctor-access.test.js
```

This starts only owned helpers/browser/Vite, invokes the existing Flask fixture,
and creates a fresh random schema/port each time. It never reuses the target above.
Clinical-review mode enables schema/user deletion in the helper after renewed
owned-instance identity checks. Default access-only mode retains its prior behavior.

Teardown closed the owned browser/Vite/backend processes, dropped only this schema
and test user, and shut down the exact owned mysqld process, PID **25076**, normally
with exit 0. The data directory was removed separately after checking its resolved
absolute path against the run identity, successful shutdown/drop receipt and absent
PID. No unrelated resource was removed. Non-secret evidence retained:

- `.local/mysql-e2e-daff9ddcd42a/identity.json`
- `.local/mysql-e2e-daff9ddcd42a/stopped.json`: running=false, exit_code=0,
  schema_dropped=true, user_dropped=true, data_directory_removed=true
- `.local/mysql-e2e-daff9ddcd42a/mysqld.log`: normal shutdown completed

Only verification files changed this turn:
`frontend/tests/e2e/doctor-access.test.js`,
`frontend/tests/e2e/disposable_mysql.py`,
`frontend/tests/e2e/mysql_review_assertions.py` (new),
`frontend/tests/flask_auth_fixture.py`, and this document.

All required feature acceptance criteria pass for the described local setup.
Cloud/production MySQL, other browsers and exhaustive concurrency schedules were
not tested. V17 runtime/provenance, independent execution safety and approved
prediction parity remain blocked and separate; no observer, security assertion,
allowlist, model-loading policy or frozen artifact/source was changed.

16 October 2026 (Asia/Calcutta). Implements human-authored review of saved
assessments in the existing React/Flask/SQLAlchemy application. V17 loading and
observer/security policy are unchanged. No prediction is requested, generated,
copied into a review or treated as a prescription by this workflow.

## Authorization and consent

Read authorization remains the existing assessment_read grant policy: authenticated
doctor identity, matching patient/owner link, issued status, exact 30-day duration,
valid consent reference, issuance/expiry boundary and no revocation. Appointments,
doctor role alone, administrator role and patient ownership do not grant review writes.

An authenticated administrator already explicitly provisioned as a
GrantAdministrator may opt in at the existing grant-issuance endpoint:

```http
POST /api/patients/{patient_id}/doctor-access-grants
Authorization: Bearer <authorized-administrator-token>
Content-Type: application/json

{"doctor_user_id": 123, "consent_reference": "retained-consent-reference", "allow_review": true}
```

The administrator must attest that the retained consent reference covers both
reading and human clinical review/prescription recording by the selected doctor.
The API records this attestation; it does not verify an external consent document.
Only JSON booleans are accepted. Omission means false; historical grants remain
false. There is no automatic upgrade, role-only opt-in or in-place grant editing.
Replace a read-only grant through the existing revoke/new-issuance workflow with
a new consent reference. This uses the existing operator/API process, not a new
public administrator screen. My Profile identifies review-enabled grants; patient
revocation stops subsequent reads and writes and retains historical review records.

## Doctor workflow and persistence

Open the existing authorized-patient directory, patient history and assessment
detail. The clinical-review panel fetches persisted review history independently.
Read-only doctors can read that history but see no write form. The doctor supplies:

- Required clinical notes, at most 4096 characters.
- Exactly the four existing recommendation names, manually entered, each nonblank
  and at most 2048 characters. Their shared names do not indicate ML provenance.
- Zero to ten manually entered prescriptions: medication, dose, route, frequency,
  duration and instructions. Each is at most 256 characters; instructions may be
  empty, and all other prescription fields must be nonblank.
- A decision permitted by the existing state graph.

The existing reason column stores clinical_notes. New JSON columns store structured
recommendations and prescriptions. Actor identity comes only from validated JWT/DB
authentication; UTC timestamps are server generated and serialized with Z. Inputs
and patient-supplied notes are never overwritten. Patient history/detail response
contracts remain unchanged; review content is exposed only through doctor routes.
There is no patient-release, dispensing, external prescription transmission or
autonomous prescribing workflow.

Existing transitions are retained:

1. pending_review -> approved or returned_for_changes.
2. returned_for_changes -> pending_review, with revised human-entered content.
3. pending_review -> approved following that resubmission.

Approved is final. Saved events cannot be updated/deleted; revisions append events
and retain earlier content. At most 100 events may be appended to one assessment.
Legacy review events with null content are marked legacy_unclassified, never
promoted to human-authored recommendation or model-inference evidence.

## API and conflict behavior

Both routes require the doctor role and a fresh active read-grant check:

```text
GET  /api/patients/{patient_id}/assessments/{assessment_id}/reviews
POST /api/patients/{patient_id}/assessments/{assessment_id}/reviews
```

GET returns assessment_id, state, version, can_review and ordered reviews. POST
requires exactly expected_version, decision, clinical_notes, recommendations and
prescriptions. Unknown fields, duplicate JSON keys, unsupported query parameters,
invalid types and oversized bodies (existing 16 KiB request limit) are rejected.
The total request limit also applies when individual fields meet their limits.

POST additionally requires allow_review on the active grant. It locks grant/patient
and assessment rows on MySQL and checks the expected event count/state. The unique
assessment/sequence key also rejects competing inserts. Stale/repeated submissions
or forbidden transitions return 409. Unauthorized access returns 401/403 and
cross-patient/missing assessments return 404 only after patient authorization.
No-store applies to successful and failed responses. Failed transactions roll back.
The service performs a narrow Core append after authorization; existing ORM and
bulk write guards continue to reject generic history mutation.

The frontend does not claim a save until the server response arrives, blocks
duplicate submissions, and reloads from persisted history on remount. Errors clear
review data and drafts; refresh before re-entering a failed submission. A 401/403
also triggers assessment access revalidation, clearing the viewer during that
request. Focus/visibility revalidation in the existing viewer remains. Revocation
is detected on subsequent requests, not instant erasure from an already open tab.
If a response is lost after commit, refresh to see the saved event before retrying.

## Migration and rollout

New revision: 0007_clinical_review, after 0006_receptionist_appointments.
It adds allow_review BOOLEAN NOT NULL DEFAULT false to patient_doctor_grants and
nullable recommendations/prescriptions JSON columns to assessment_reviews.
No consent/review decisions or model outputs are backfilled. Existing rows retain
their prior meaning. Apply this revision through the established deployment
migration process before serving the updated application. No existing database
was migrated during implementation.

Downgrading 0007 drops the three columns and destroys their content; back up first.
On SQLite, commit that rollback to 0006 before separately downgrading through
0006's historical role-table rebuild, which requires a fresh dedicated transaction.
The three historical migration tests explicitly stage this boundary. The old
migration safety guard was not changed. The new revision's SQLite roundtrip and
model/schema agreement were tested; live MySQL upgrade/downgrade and contention
were not run.

## Verification actually executed

- New clinical-review backend suite: 12 passed against migrated in-memory SQLite,
  with V17 load/predict patched to fail if invoked. Covers human content, reload,
  actor/time, role/owner/patient boundaries, explicit review consent, read-only
  grants, expiry/revocation, validation, conflicts, revision history, transaction
  rollback and migration roundtrip.
- First affected backend regression run: 127 tests, three errors from historical
  SQLite multi-revision downgrade transaction requirements. The three migration
  tests passed after staging the new rollback; final affected run: **127 passed**.
- Frontend service/state regressions: **55 passed**, including six new review tests.
- New review render tests: **4 passed**; existing doctor/patient render tests:
  **18 passed**. These are state/SSR tests, not browser interactions.
- Receptionist frontend regressions: **3 passed**. The initial restricted-sandbox
  run passed two and failed its Vite render test with spawn EPERM; the same command
  outside that restriction passed all three. Total frontend checks: **80 passed**.
- Production bundle: write:false build passed, 41 modules, no dist output written.
- Existing doctor-access E2E expected migration head updated to 0007; browser/E2E
  and live MySQL were **not rerun**. Prior browser/MySQL passes cover the earlier
  access workflow only and do not establish clinical-review acceptance.

Commands used (backend from repository root):

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_clinical_reviews.py' -v
@'
import sys, unittest
sys.path.insert(0, 'tests/backend')
names=['test_clinical_reviews','test_reviews','test_access_grants','test_doctor_directory','test_patients','test_reception','test_assessment_prediction','test_foundation','test_database','test_v17_startup_safety']
r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(not r.wasSuccessful())
'@ | .venv/Scripts/python.exe -B -
```

Frontend commands from frontend/:

```powershell
node --test --test-isolation=none tests/clinical-review.test.js tests/doctor.test.js tests/patient.test.js tests/assessment-prediction.test.js tests/session.test.js tests/foundation.test.js
node --test --test-isolation=none tests/clinical-review-render.test.js
node --test --test-isolation=none tests/doctor-render.test.js tests/patient-render.test.js
node --test --test-isolation=none tests/reception.test.js
node --input-type=module -e "import { build } from 'vite'; await build({ build: { write: false } });"
```

No independent V17 runtime/provenance, observer containment, real inference or
prediction-parity acceptance follows from these application tests. The next useful
verification is a disposable browser/backend review scenario, followed by disposable
MySQL migration and concurrency verification. No packages or tools were installed.

## Files changed for this feature

- Backend: `backend/app/api/__init__.py`, `backend/app/api/access_grants.py`,
  `backend/app/api/clinical_reviews.py`, `backend/app/auth/grants.py`,
  `backend/app/models/access_grant.py`, `backend/app/models/review.py`,
  `backend/migrations/versions/0007_clinical_review.py`.
- Frontend: `frontend/src/auth/AuthContext.jsx`, `frontend/src/doctor/review.js`,
  `frontend/src/pages/DoctorReviewPanel.jsx`,
  `frontend/src/pages/DoctorAssessmentsPage.jsx`,
  `frontend/src/pages/PatientProfilePage.jsx`, `frontend/src/services/patients.js`.
- Backend tests: `tests/backend/test_clinical_reviews.py`,
  `tests/backend/test_reviews.py`, `tests/backend/test_foundation.py`,
  `tests/backend/test_access_grants.py`, `tests/backend/test_patients.py`.
- Frontend tests: `frontend/tests/clinical-review.test.js`,
  `frontend/tests/clinical-review-render.test.js`,
  `frontend/tests/e2e/doctor-access.test.js` (migration-head expectation only).
- Documentation: `docs/setup/doctor-clinical-review.md`,
  `docs/setup/doctor-assessment-viewer.md`,
  `docs/setup/patient-doctor-access-grants.md`.

Pre-existing observer/security changes and `tests/backend/test_v17_startup_safety.py`
were preserved, not edited for this feature. Both frozen artifact/source SHA-256
values were checked after implementation and still match their approved identities.
