# Patient Assessment UI — 13 October 2026 (Asia/Calcutta)

## Scope and inspection

This implements the missing patient assessment milestone. The earlier frontend
foundation only implemented account screens; it had no patient profile, assessment
form, history or detail UI. Inspected all current frontend source/tests, the
frontend-foundation and patient-assessment-apis reports, backend patient routes,
assessment_validation.py, existing backend patient tests and frozen V17 field
constants before editing. The V17 training source was read/AST-parsed only, never
executed. No applicable AGENTS.md was found. Git is not initialized in this workspace.

The existing React/Vite/JavaScript/Bootstrap application, routing, authentication,
API client and test conventions were reused. No packages, backend files, endpoints
or migrations were added/changed. No inference, review actions, doctor access, PDF,
cloud or Docker work was performed. Work stops at this milestone.

## New screens and exact contracts

Patient navigation now links to these protected hash routes:

| Route | Implementation | Behavior |
| --- | --- | --- |
| #/patient/profile | src/pages/PatientProfilePage.jsx | Load own profile; create it only when GET /me returns 404 |
| #/patient/assessments/new | src/pages/AssessmentFormPage.jsx | Enter, validate and save all 12 inputs plus optional notes |
| #/patient/assessments | src/pages/AssessmentHistoryPage.jsx | Empty state, saved records, pagination and failed-request retry |
| #/patient/assessments/{assessment_id} | src/pages/AssessmentDetailPage.jsx | Retrieve saved inputs/notes or identify an older record with no inputs |

PatientWorkspacePage.jsx connects the screens to an in-memory observable workspace
and the authenticated patient service. Profile IDs come from GET /api/patients/me,
not a client-selected owner or URL patient ID. Profile creation sends `{}` to POST
/api/patients. Its response has only `{patient: {id, owner_user_id}}`; no demographics,
edit operation or extra profile fields were invented. A duplicate/racing creation
(409) retrieves the already existing own profile. Other failed profile requests
show an error/retry and never masquerade as a missing profile.

The frontend routes permit patients only. Existing Flask patient-role and ownership
checks remain the authorization boundary. Real API tests prove cross-owner requests
return 404, doctor/admin requests return 403, and invalid bearer requests return 401.
Navigation restrictions do not claim to replace those checks.

Assessment creation sends `{inputs: {all twelve exact keys}, notes?: string}` to
POST /api/patients/{own_profile_id}/assessments. Notes are omitted when not supplied;
entered notes and categorical text are preserved, including whitespace. No actor,
owner, timestamp, review, prediction or output fields are submitted.

| Exact required input name | JSON type |
| --- | --- |
| Disease | Nonblank string |
| Symptom Severity | Nonblank string |
| Nadi Reading | Nonblank string |
| Constitution/Prakriti | Nonblank string |
| Stress Levels | Nonblank string |
| Sleep Patterns | Nonblank string |
| Age Group | Nonblank string |
| Physical Activity Levels | Nonblank string |
| BP Systolic | Finite number |
| BP Diastolic | Finite number |
| Pulse Rate | Finite number |
| Weight (kg) | Finite number |

The eight categorical controls are free text: no allowed vocabularies were invented.
Numeric controls use step="any" without medical min/max ranges, presets or defaults.
Every field starts blank. Missing/blank numeric inputs fail validation before number
conversion; explicit zero remains zero. Numeric strings from HTML controls are
explicitly converted to JSON numbers only after validation. Text checks match the
backend's technical limits (256 code points per category, 4096 for notes), NUL/invalid
Unicode rejection and 16 KiB serialized UTF-8 request cap. These are structural
checks, not medical validation. The real-API test compares frontend names/types with
both the backend constants and AST-parsed frozen V17 declarations.

Submission displays field validation, saving/loading, safe network/authorization/API
errors and success with a link to the actual saved assessment. Concurrent double
submission is blocked. Failed saves retain the draft; successful saves show the
returned record ID. Start another assessment explicitly resets the form to blanks.
Saving and detail screens state: "Saving an assessment does not generate predictions
yet." No fabricated clinical recommendations/results are displayed.

History calls GET /api/patients/{id}/assessments?limit=20&after_id={cursor}. Load more
follows the actual next_after_id; failed pagination preserves previous records and
its cursor for retry. History is in ascending record-ID order as provided by Flask.
Detail calls GET /api/patients/{id}/assessments/{assessment_id}. The service validates
response structure and patient linkage. Older records with inputs:null remain null;
the UI displays their absence without filling in zero/empty input objects. Recorded
timestamps are displayed as server-supplied values without an invented timezone.
Late/unmounted requests and obsolete detail responses cannot overwrite current state.
Drafts/results are in memory; reload/logout does not persist patient data locally.

## Reuse and limited existing-file changes

AuthContext.jsx has only additive patient-service wiring: construct the service
with the same existing client and expose it to the new screens. Login, registration,
JWT handling, the session implementation and the API client were not rewritten.
The existing client contains authentication-specific copy for 400/409/503; the new
patient service maps those statuses to patient-specific copy while preserving the
client's bearer/session-failure handling. services/api.js, services/auth.js,
auth/session.js and pages/AuthPage.jsx are byte-identical to the inspected baseline.
The original authentication tests still pass.

Router.jsx/routes.js gained four patient-only routes. AppShell.jsx and HomePage.jsx
gained patient navigation; doctor/admin navigation did not gain patient controls.
styles.css gained responsive page width and whitespace/wrapping for saved text.
The existing Flask test fixture gained an opt-in --patient-fixtures branch with
only disposable legacy accounts/records and safe contract constants output.
The existing render.test.js now disables unneeded HMR/WebSocket servers to avoid
fixed-port collisions with concurrent render tests. Application Vite config is
unchanged. Initial frontend runs passed all tests but produced a WebSocket port
warning; after this test-only fix the final run passed without that warning.

## Test evidence specific to this milestone

New frontend/tests/patient-render.test.js tests the actual screen components and
calls their actual input/change/create/submit/reset/load-more handlers with the
workspace, in addition to rendering their state to HTML:

- Patient profile screen shows loading, missing profile, actual create handler and owner-linked result
- Clinical assessment form renders all 12 exact named required inputs with text/number types and no medical ranges
- Assessment form input/change/submit handlers validate, display loading and save actual numeric payload
- Profile/form/history/detail render network and authorization error alerts with retries where appropriate
- Assessment history renders empty/loading states, records, detail links and load-more handler
- Assessment detail renders all saved inputs, explicit zero, notes, and preserves null legacy records

New frontend/tests/patient.test.js tests the shared validation, protected routes,
service and workspace behavior:

- all twelve fields are required, exact types preserve explicit zero and supplied text
- patient profile, assessment form, history and detail routes deny anonymous and privileged roles
- profile service sends only empty creation body and recovers a duplicate profile race
- patient error copy handles missing profile, validation, 401, 403, unavailable service and network failures
- malformed patient responses fail closed and null legacy inputs are preserved
- profile loading, missing state, creation success and retry after failed requests
- submission validates before requests, prevents duplicate writes, retains drafts after failure and records success
- history handles empty state, pagination, failed load-more retry and detail errors
- unmounted patient workspace ignores late responses and stale detail loads cannot overwrite the newest request

New frontend/tests/patient-contract.test.js runs "Patient Assessment UI operations
through Vite proxy and real owner-only Flask persistence", with these seven real-API
subtests:

- 12 exact frontend field names and types agree with backend and parsed frozen V17 declarations
- missing legacy profile is viewed, created with empty body and retrieved for authenticated owner
- registration profile is reused and assessment form submission persists all inputs, zero, notes and actor
- real Flask rejects each missing field, wrong numeric type and client-supplied ownership
- assessment history paginates actual records and detail preserves legacy null inputs
- new patient history is empty; another patient cannot view, create or retrieve owner records
- doctor/admin operations remain forbidden and invalid tokens trigger existing logout handling

The integration test starts real Vite and Flask on ephemeral loopback ports, with an
isolated SQLite in-memory database migrated to head, generated test-only JWT secret
and disposable accounts. It verifies 23 actual assessment rows across history pages,
legacy null detail, submitted input/notes roundtrip and owner/actor linkage. Both
servers are stopped by test cleanup. There is no mock clinical output, production
database access or real patient data. Tests require the root .venv with existing
backend dependencies; AYURSAGE_TEST_PYTHON can select another suitable interpreter.

## Final required verification

Exact commands executed from the frontend directory:

```powershell
cd C:\Users\yvasa\Videos\PROJECT-Ayursage\frontend
npm test
npm run build
```

Final test outcome: exit 0, **36 tests passed, 0 failed/skipped**, 5.783 seconds.
This includes all 13 original tests plus 23 new tests/subtests, including the
integration parent. Final build: exit 0, Vite 8.3.4, 35 modules transformed, 531 ms;
index.html 0.44 kB, CSS 231.33 kB, JS 249.35 kB (77.24 kB gzip). Normal process access
was approved for Vite and loopback/child-process tests, as in the previous milestone.
No new dependency or install was needed.

Exact commands executed from the workspace root:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

All exit 0: **93 backend tests passed in 11.590 seconds**, `No broken requirements
found`, and the same **10 route operations**. Existing backend ownership, exact
frozen-source field names, structural validation, legacy records, pagination,
RBAC and review-denial tests remain passing. No backend code was changed.

A pre/post SHA-256 inventory comparison confirmed all 52 existing non-bytecode
files under backend, ml, infra, tests/backend, tests/ml and tests/integration are
unchanged, plus .gitignore (53 protected files total). Also verified unchanged
frontend API/auth service/session/login files, package.json, package-lock.json and
vite.config.js. No protected file was added/removed. The temporary inventory was
removed after comparison. No Git diff or tracked-file claim is made.

## Exact changed files

Added:

- frontend/src/pages/PatientProfilePage.jsx — profile screen and reusable patient error feedback
- frontend/src/pages/AssessmentFormPage.jsx — 12-field form, errors, saving and success
- frontend/src/pages/AssessmentHistoryPage.jsx — history/empty/error/pagination UI
- frontend/src/pages/AssessmentDetailPage.jsx — retrieved inputs/notes and legacy absence
- frontend/src/pages/PatientWorkspacePage.jsx — React lifecycle and screen/data wiring
- frontend/src/patient/assessmentFields.js — exact field names, types and payload validation
- frontend/src/patient/workspace.js — profile/form/history/detail state and operations
- frontend/src/services/patients.js — existing owner-only endpoint contracts and safe response/errors
- frontend/tests/patient.test.js — validation, route, service and operation-state tests
- frontend/tests/patient-render.test.js — rendered screens and actual UI-handler tests
- frontend/tests/patient-contract.test.js — real Flask/Vite-proxy patient integration tests
- docs/setup/patient-assessment-ui.md — this milestone report

Updated:

- frontend/src/auth/AuthContext.jsx — additive same-client patient-service binding
- frontend/src/components/AppShell.jsx — patient navigation and shell footer
- frontend/src/pages/HomePage.jsx — patient navigation and current screen availability
- frontend/src/routing/Router.jsx — patient workspace dispatch
- frontend/src/routing/routes.js — patient-only profile/form/history/detail routes
- frontend/src/styles.css — patient page width and saved-text wrapping
- frontend/tests/flask_auth_fixture.py — opt-in isolated legacy/profile/assessment fixtures and contract evidence
- frontend/tests/render.test.js — disable test-only HMR/WebSocket listeners
- README.md — link this milestone and describe patient UI availability

Ignored generated output: frontend/dist and Vite caches under node_modules.

## Not tested and stopping point

The browser inventory was empty. No mounted browser click-through, browser focus
behavior, visual/responsive screenshot review or assistive-technology checks were
performed. Component-render/actual-handler tests and real API/proxy tests passed;
these do not substitute for browser end-to-end verification. No live MySQL,
external-origin CORS, clean install, Docker/cloud deployment, PDFs, V17 loading or
inference, or watchdog acceptance tests were performed. Patient-doctor grants and
review policy remain unimplemented; doctor data access and review actions remain
blocked. This milestone implements patient data entry/retrieval only and stops here.
