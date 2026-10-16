# AYUR-SAGE system map: confirmed four-role design

## Approved PDF report slice - 16 October 2026

Approval-bound immutable PDFs now extend the verified doctor clinical-review
workflow. Review-enabled doctors explicitly issue one version-1 report; patients
retrieve only their own issued report. Every doctor report request rechecks the
current grant. Read-only/revoked grants and administrator role do not authorize
reports. Private objects are separate from SQL metadata; signed application download
links expire after 900 seconds and still require JWT and current authorization.
Migration head is now **0008_clinical_reports**. Production storage is intentionally
unconfigured; local verification uses an explicitly injected private test adapter.
See [report implementation and evidence](../setup/clinical-pdf-reports.md) for
API contracts, deployment prerequisites, failure recovery, tests and exact files.
This supersedes historical report-absence claims below; it does not enable V17
inference or change any observer/security acceptance gate.

## Current application milestones — 16 October 2026

**Doctor clinical review: VERIFIED for the tested disposable scenarios.**
[Clinical-review evidence](../setup/doctor-clinical-review.md) records MySQL 8.0.46
0006 -> 0007 migration/preservation, three independent-connection contention
trials (201/409), seven browser/backend stages, 127 SQLite backend regressions,
80 frontend regressions and the in-memory build. These are retained acceptance
results, not a claim that this follow-up reran that milestone. Reopen only for a
specific regression. Production/cloud, other browsers and exhaustive schedules
remain outside that acceptance.

**Next application slice implemented: administrator grant-management UI.**
`#/admin/grants` now completes the existing issue/list/revoke API workflow. It
requires the admin role in the UI and the existing explicit GrantAdministrator
permission at the backend, retained-consent attestation, positive patient/doctor
IDs, confirmation, 30-day expiry and explicit review opt-in (default false).
No backend policy or schema change was required. See
[administrator grant UI](../setup/admin-grant-management.md) for current tests,
browser evidence, operator steps and limits. This does not add staff provisioning,
patient search, clinical reads or release authority to administrators.

The application remains React/Vite -> Flask -> SQLAlchemy/MySQL. Migration head
is 0007_clinical_review. Patient grant revocation, doctor directory/detail/review
and receptionist features supersede the absence/read-only claims in the historical
sections below. V17 runtime/provenance, observer security/execution safety and
independent prediction-parity gates remain **BLOCKED and unchanged**. No inference
or patient-result-release policy follows from human clinical review verification.

## Current receptionist slice — 14 October 2026

Receptionist identity, exact-email administrative lookup, manual appointment
creation/list/reschedule, cancellation, check-in, completion and no-show are now
implemented under the approved policies. See [receptionist-module.md](../setup/receptionist-module.md)
for files, endpoints, migration, backup, tests, live HTTP evidence and limits.

| Concern | Current source and acceptance | Remaining boundary |
| --- | --- | --- |
| Receptionist identity | Fourth role `receptionist`; existing trusted provisioning CLI; no public staff registration; `#/receptionist` protected dashboard | No general admin account-management UI |
| Administrative data | `api/reception.py` receptionist-only exact-email lookup returns patient ID/email/registration status; doctor ID/email directory | No clinical serializer, credentials or grant-management authority |
| Scheduling/attendance | `models/appointment.py`, migration `0006_receptionist_appointments`; default 30-minute UTC intervals, serialized patient/doctor overlap checks, approved state transitions and attributed event records | Manual doctor availability; no invented hours or recurring schedule; live MySQL concurrency unverified |
| Invitations | Approved 24-hour, patient-only email, hashed single-use token and atomic patient-password setup policy is recorded | Dedicated delivery service/sender/setup-link configuration absent; issuance/setup/status paths remain isolated; no tokens or delivery-success claims |
| Verification | Approved local SQLite backed up and migrated 0005 → 0006; original records preserved; 123 backend and 39 frontend tests, build/pip check and actual receptionist HTTP acceptance pass | Browser unavailable. Full receptionist module remains incomplete pending invitations |

The approved appointment transitions are scheduled → checked_in/cancelled/no_show,
checked_in → completed, terminal completed/cancelled/no_show. Reschedule/cancel is
denied after check-in. Any receptionist can manage appointments. Receptionists and
administrators still have no automatic clinical access; appointments are never
patient–doctor grants. Prior grant policy and review-write blockers remain unchanged.
Both existing frontend listeners (5173 and 5174) were preserved; live checks used 5173.

The earlier grant follow-up and original reconciliation below retain their historical
evidence; this section supersedes their receptionist-absence and migration-head claims.

## Current implementation follow-up: assessment-read grants

Updated 14 October 2026. The following rows supersede the original read-only reconciliation
below for this backend slice. Full evidence and deployment instructions:
[patient-doctor-access-grants.md](../setup/patient-doctor-access-grants.md).

| Concern | Current implementation | Remaining boundary |
| --- | --- | --- |
| Grant policy | Explicitly authorized administrator only; mandatory recorded consent reference; owner or authorized administrator revocation; fixed assessment-read scope; mandatory 30-day expiry | The issuing administrator attests to externally retained consent evidence; the API does not independently verify its authenticity. Review and release policy remain separate |
| Grant data | `models/access_grant.py::{GrantAdministrator,PatientDoctorGrant}`; additive `0005_patient_doctor_grants` after unchanged 0004; FK-linked consent owner/doctor/issuer and issuance/revocation history; no automatic admin authorization; approved local `.local/auth/auth.sqlite3` backed up and migrated 0004 → 0005 | Live MySQL unverified; general audit-event service remains absent |
| Grant administration | `auth/__init__.py` CLI `authorize-grant-administrator`; `api/access_grants.py` issue/list/revoke under existing patient blueprint; owner-scoped metadata listing supports revocation | Local operator authorizes admins; no new staff provisioning/role-management UI or general delegation service |
| Clinical reads | Existing assessment history/detail GETs accept owner or doctor with valid explicit grant; `auth/grants.py` rechecks scope, owner link, status, revocation and expiry on every request | Profiles, writes and review actions stay denied for doctors; admins get no clinical read bypass; doctor UI remains a placeholder |
| Verification | Historical grant acceptance: 16 focused grant tests, 113 complete backend tests, 36 frontend tests, build/pip check and approved local SQLite/HTTP grant acceptance. Current receptionist slice above adds role provisioning and retains grant-denial/revocation regressions | No browser interaction or live MySQL verification |

No receptionist/appointment module, model loading, prediction, prescription or
care-note operation was enabled. Frontend code and ports, environment configuration,
V17, watchdog and Docker/WSL resources were unchanged. The original plan's broader
four-role policy/audit work and doctor review steps remain pending; its immediate
recommendation below predates this implemented assessment-read grant slice.

## Original reconciliation and target design

Reconciled 13 October 2026 (Asia/Calcutta). Scope: read-only inspection of repository source, migrations, tests and existing reports, plus unauthenticated HTTP readiness GETs. Only this document was changed. No model/training execution, database inspection or migration, account creation, test execution, dependency installation, worker launch, loading-control change or Docker operation was performed. Existing test results below are historical evidence, not fresh passes. Git is not initialized in this workspace; no Git diff/commit claim is made.

## Problem, architecture and complete workflow

AYUR-SAGE is an AI-based Ayurvedic treatment and diet recommendation system. It needs to connect patient registration and clinical input collection to authorized doctor review and an explicitly released care record, while keeping administrative work separate from clinical authority. V17 supplies four recommendation labels; it does not prescribe medication, establish clinical efficacy or supply a fifth diet output. Diet enrichment needs a separate verified policy and evidence.

The existing architecture is React/Vite/JavaScript/Bootstrap → one modular Flask REST application → Flask-SQLAlchemy/Alembic, targeting MySQL/PyMySQL. SQLite supports isolated tests and the explicit local-development launcher. Future inference belongs behind Flask orchestration using the existing `ml/` boundary; no second backend or new deployed ML service is required by this design. Cloud report storage and deployment remain targets, not implemented services.

The complete target workflow is:

1. Patient self-registers, or a receptionist assists registration through an approved administrative flow. Identity, patient ownership and consent/account activation must remain explicit. Staff are provisioned by an authorized operator/administrator, never by public role selection.
2. Receptionist schedules an appointment and records check-in/attendance and administrative status. Neither an appointment nor check-in automatically grants clinical access to a doctor or receptionist.
3. Patient supplies the 12 clinical inputs and optional patient notes. Flask authenticates, authorizes, validates and persists an assessment. History and status are visible within patient scope.
4. An explicit patient–doctor grant/assignment authorizes the appropriate doctor to access the patient and review the assessment. Revocation, expiry and scope must be checked on every operation; assessment authorship and role membership are not grants.
5. After independent V17 loading/compatibility gates pass, an authorized prediction operation snapshots validated inputs, runs the frozen four-label adapter and records provenance/status. Failures do not create successful recommendations. Saving an assessment alone does not currently run inference.
6. The assigned/authorized doctor reviews inputs and model suggestions, records a clinical decision, and manually writes **Doctor Prescription & Care Notes**. Model outputs, patient-supplied notes and doctor-authored care notes remain separate records/fields. A placeholder is not doctor approval.
7. Under an explicit release policy, the patient receives authorized results, care notes and reports. Returned assessments follow the approved correction/resubmission policy; current APIs have no update/resubmit operation.
8. Account changes, grants, sensitive access, administrative events, prediction/review/release actions and operations produce appropriate audit events. Administrator audit visibility does not imply unrestricted clinical content access.

Currently only self-registration → login → own minimal patient profile → assessment creation/history/detail is implemented. The remaining steps are target design.

## Four actors, screens and permissions

The confirmed business roles are Patient, Receptionist, Doctor and Administrator. Keep the existing `admin` code for Administrator; adding `receptionist` requires an additive migration and coordinated backend/frontend contract changes. Current `ROLE_CODES`, role check constraint, migration seeds and frontend role maps contain only `patient`, `doctor`, `admin`.

| Actor | Authorized target responsibilities/screens | Denied by default | Verified implementation |
| --- | --- | --- | --- |
| Patient | Own profile, assessment submission/history/status, authorized results and reports; existing patient workspace should be extended | Other patients; staff provisioning/role/grant administration; doctor decisions and prescriptions; unreleased clinical results | `#/patient` home; `#/patient/profile`; `#/patient/assessments/new`; `#/patient/assessments`; `#/patient/assessments/:id`. Profile is only IDs; saved assessment views have no review status/results/reports |
| Receptionist | Assisted patient registration, scheduling, check-in/attendance, administrative tracking; proposed receptionist workspace using the shared shell/authentication | Clinical assessments, predictions, prescriptions, doctor notes and clinical review actions unless a specific permission is explicitly approved; staff role/grant administration by receptionist identity alone | No role code, seed, screen, route, provisioning option, model or API found for this role or appointments/check-in |
| Doctor | Only assigned/authorized patients; assessment/recommendation review; clinical decisions and manual prescription/care notes; extend existing doctor home into worklist/detail/review views | Unassigned patients, absent/expired/revoked grants; role provisioning; unapproved data release; role-only access | `#/doctor` resolves to shared `HomePage`, account details and unavailable-feature text. All current patient APIs deny doctors; no clinical doctor workflow |
| Administrator (`admin`) | Authorized provisioning, role management, access-grant administration, audit visibility and operations; extend existing administrator home | Automatic/unrestricted patient-data access; doctor review/prescription authority merely from admin status; arbitrary clinical access through audit/report tools | `#/admin` shared placeholder home. Local operator CLI provisions doctor/admin accounts; no administrator management HTTP/UI workflow |

Backend authorization is decisive; hash route guards are presentation only. `backend/app/auth/security.py::authenticate` validates HS256 bearer JWT claims, then reloads user/role from the database. `auth_required`, `roles_required` and `require_patient_owner` enforce the current policy. `backend/app/api/patients.py::owned_patient` filters ownership before reading records and returns the same 404 for another owner's or missing patient ID. `recorded_by_user_id` is attribution, not access authority. No privileged ownership override exists.

Target receptionist exceptions require explicit approved action/resource scopes; do not solve assisted registration by granting clinical reads or making the receptionist the patient's owner. Administrator grant administration must itself be authorized and auditable. The exact grant issuer, delegation limits, patient consent and result-release policy still require specification; they are not inferred from the four role names.

## Implementation map and evidence

| Concern | Exact current file/function references | Test references and gap |
| --- | --- | --- |
| Single application/API | `backend/app/__init__.py::create_app`; `backend/app/api/__init__.py::api`; `backend/app/api/health.py::health`; `backend/config/__init__.py::load_config` | `tests/backend/test_foundation.py::test_only_milestone_routes_registered`, `test_health`, `test_unhandled_error_does_not_expose_details`. Only health/auth/patient routes registered |
| Persistence | `backend/app/database/__init__.py::init_database`, `validate_database_url`, `enable_sqlite_foreign_keys`; `backend/app/models/__init__.py` | `tests/backend/test_database.py::test_migration_matches_models_and_is_repeatable`, `test_foreign_keys_are_enforced`, `test_role_constraints`, `test_mysql_configuration_does_not_connect_at_startup`. Tests do not establish live MySQL acceptance |
| Signup/login/provisioning | `backend/app/auth/routes.py::credentials`, `create_account`, `register`, `login`, `me`; `backend/app/auth/__init__.py::init_auth` nested `create_privileged_user` | `tests/backend/test_auth.py::test_registration_hash_and_patient_profile`, `test_no_public_privileged_assignment`, `test_all_role_permissions_and_cli_provisioning`, `test_cli_rejects_duplicate_invalid_and_uncontrolled_roles`. No receptionist or admin HTTP provisioning |
| Authorization | `backend/app/auth/security.py::authenticate`, `roles_required`, `require_patient_owner`; `backend/app/api/patients.py::owned_patient` | `tests/backend/test_auth.py::test_ownership_denies_nonowners_and_privileged_roles`, `test_database_role_changes_take_effect_for_existing_token`; `tests/backend/test_patients.py::test_doctor_and_administrator_denied_every_read_and_write`, `test_cross_patient_and_nonexistent_ids_are_indistinguishable`, `test_assessment_cannot_be_read_via_another_owned_patient_path`. No grants/approved exceptions |
| Assessment contract | `backend/app/api/assessment_validation.py::assessment_payload`, `json_object`; `backend/app/api/patients.py::create_assessment`, `assessment_data`, `list_assessments`, `get_assessment` | `tests/backend/test_patients.py::test_assessment_roundtrip_and_actor_from_authentication`, `test_all_twelve_inputs_are_required_with_exact_names`, `test_feature_and_output_names_match_frozen_source_without_importing_it`, `test_legacy_assessments_keep_null_inputs`. Structural validation only |
| Reserved review history | `backend/app/models/review.py::AssessmentReview`, `validate_review_transition`, `protect_review_history`, `block_review_dml`; `ClinicalAssessment.review_state` | `tests/backend/test_reviews.py::test_decision_writes_are_blocked_for_all_actors_and_states`, `test_patient_and_privileged_roles_cannot_use_review_http_actions`, `test_session_bulk_dml_cannot_bypass_guards`, `test_inconsistent_history_cannot_project_an_approved_state`. ORM/session protections are not DB-wide immutability or authorized concurrent append |
| Frontend composition | `frontend/src/routing/routes.js::roleRoutes`, `resolveRoute`; `routing/Router.jsx::Router`; `pages/HomePage.jsx::HomePage`; `pages/PatientWorkspacePage.jsx::PatientWorkspacePage`; `patient/workspace.js::createPatientWorkspace` | `frontend/tests/foundation.test.js`: “anonymous users and every role are guarded on every role route”; `frontend/tests/patient.test.js`: “patient profile, assessment form, history and detail routes deny anonymous and privileged roles”. Three role maps only |
| Existing patient screens | `pages/PatientProfilePage.jsx::ProfileScreen`; `AssessmentFormPage.jsx::AssessmentFormScreen`; `AssessmentHistoryPage.jsx::AssessmentHistoryScreen`; `AssessmentDetailPage.jsx::AssessmentDetailScreen` under `frontend/src/` | `frontend/tests/patient-render.test.js`: “Clinical assessment form renders all 12 exact named required inputs with text/number types and no medical ranges”, “Assessment detail renders all saved inputs, explicit zero, notes, and preserves null legacy records”. Extend these screens; do not create a second assessment form/history |
| HTTP integration/session | `frontend/src/services/api.js::createApiClient`; `services/auth.js::createAuthService`; `services/patients.js::createPatientService`; `auth/AuthContext.jsx::AuthProvider`; `auth/session.js::createSession` | `frontend/tests/flask-contract.test.js`: “Vite HTTP entry and proxy with real Flask auth, migrated disposable SQLite and all three roles”; `frontend/tests/patient-contract.test.js`: “Patient Assessment UI operations through Vite proxy and real owner-only Flask persistence”; `frontend/tests/session.test.js` covers expiry/logout. These are not complete mounted browser acceptance |

## Database: current entities and missing target entities

Migration chain is `0001_database_foundation` → `0002_password_hash` → `0003_assessment_inputs` → `0004_assessment_reviews`, in `backend/migrations/versions/`. This is repository schema intent; no live database schema was queried during reconciliation.

| Entity | Current columns/relationships | Target gap |
| --- | --- | --- |
| `Role` / `roles` | ID, unique constrained code; seeded patient/doctor/admin by 0001 | Receptionist absent. Current single-role membership is `User.role_id`; scoped permissions need explicit design, not an assumed multi-role system |
| `User` / `users` | ID, unique email, role FK; nullable password hash added by 0002 | No staff invitation/activation, account-disable lifecycle, admin provisioning/role-change service, token revocation or provisioning audit |
| `Patient` / `patients` | ID; required unique owner user FK; one profile per owner | No demographics/contact/administrative registration fields or delegated registration semantics; no edit API |
| `ClinicalAssessment` / `clinical_assessments` | Patient FK, recording-user FK, server timestamp, nullable patient notes, nullable JSON inputs added by 0003 | No inference run/result/release linkage. Legacy inputs stay NULL. No update/correction/version lifecycle |
| `AssessmentReview` / `assessment_reviews` | Assessment/actor FKs, sequence, from/to states, server decision timestamp, optional reason; unique assessment/sequence and transition constraints, 0004 | Reserved rather than usable. All application inserts blocked; no HTTP actions. No prediction linkage, care-notes field or release record |
| Appointment | Absent | Patient, scheduled provider/time, status, creator/change attribution, conflict/cancellation policy; scheduling must not substitute for grants |
| Check-in/attendance | Absent | Appointment/patient linkage, event/status/time/actor; keep administrative and clinical status distinct |
| Patient–doctor access grant | Absent | Explicit patient/doctor/action scope, issuer, grant/revoke/expiry metadata and authoritative authorization checks; define who may issue it |
| Prediction run/result | Absent | Assessment/input snapshot, actor, status/failure/idempotency, artifact/source/runtime versions/hashes, exact four outputs and creation time; separate raw suggestions from doctor-approved care |
| Doctor prescription/care notes | Absent | Doctor-authored field/record tied to authorized patient/assessment and review/version; separate from patient `notes` and model outputs |
| Report/release | Absent | Reviewed content/version, release actor/time, patient visibility, generation status and storage/access metadata; authenticated access on every fetch/download |
| Audit event | Absent | Actor/action/resource/time/outcome and appropriate correlation; restricted visibility and retention. Do not log credentials, JWTs or unnecessary clinical payloads |

Review graph currently reserves `pending_review → approved`, `pending_review → returned_for_changes`, `returned_for_changes → pending_review`. `ClinicalAssessment.review_state` projects validated ordered history, starting pending; it is **not serialized** by `assessment_data`. No prediction is implied by pending status. Raw SQL can bypass application ORM gates; current constraints validate transitions/links but do not implement full authorization, sequence-chain enforcement or append-only history at all database boundaries.

## Registration and account provisioning

Current public `POST /api/auth/register` accepts exactly email/password, normalizes email, validates a 12–128 character password, stores a salted scrypt hash, and atomically creates a patient `User` and `Patient` via `create_account`. Duplicate normalized accounts return 409. It returns user identity without a token. `AuthPage` shows success and a sign-in link. Login accepts a 1–128 character password, returns JWT, then `createAuthService.login` calls `/auth/me` before establishing identity/session. Token/identity live in memory; logout/expiry clears them. No refresh/logout/revocation endpoint exists.

Legacy patient accounts lacking a profile can create their own with `POST /api/patients` body `{}`. Registration already creates that profile; the UI/service reuses it, and handles a duplicate-profile race by re-fetching `/patients/me`. Patient ownership cannot be supplied in the request. Legacy accounts without a password hash cannot authenticate.

Current staff provisioning is Flask CLI `create-privileged-user` (`init_auth`), restricted to `doctor` or `admin`, with hidden password confirmation and standard validation. This relies on trusted local operator access; it is not an administrator-authenticated web action. No accounts are seeded by migrations. Receptionist provisioning is currently unsupported.

Target: reuse account creation/security primitives for authorized staff provisioning and role management, with explicit actor permission and audit, while keeping public signup patient-only. Assisted patient registration needs its own narrowly authorized administrative operation using the same patient/account entities, a patient-owned activation/credential flow and duplicate handling. No receptionist access to patient credentials or clinical data is implied. Bootstrap of the first administrator and later admin delegation must be documented separately from public registration.

Standard `load_config` reads process environment only; factory startup does not load `.env`, connect eagerly or migrate. `backend/local.py::prepare_local_app` is an explicit local launcher that configures `.local/auth/auth.sqlite3` and a persistent generated key, and upgrades that selected local database. It is not a production provisioning/migration mechanism.

## Actual frontend-to-Flask contracts

`AuthProvider` uses `VITE_API_BASE_URL || '/api'`. `createApiClient` appends the following relative paths, sends JSON/Accept headers, omits cookies (`credentials: 'omit'`), disables caching and adds `Authorization: Bearer <token>` only for authenticated calls. `frontend/vite.config.js` proxies `/api` unchanged to `FLASK_API_PROXY_TARGET || http://127.0.0.1:5000`; default frontend port is 5173, while existing debugging reports/tasks use explicit 5174. Browser hash paths are not Flask endpoints.

| Flask method/path | Request | Success response | Implementing function/client |
| --- | --- | --- | --- |
| GET `/api/health` | None | 200 `{"status":"ok"}`; liveness only | `health`; no clinical service |
| POST `/api/auth/register` | Exactly `{email, password}`; JSON, 4 KiB cap | 201 `{user:{id,email,role}}` | `register`; `createAuthService.register` |
| POST `/api/auth/login` | Exactly `{email, password}`; JSON, 4 KiB cap | 200 `{access_token,token_type:"Bearer",expires_in}` (default 900 seconds) | `login`; `createAuthService.login` |
| GET `/api/auth/me` | Bearer | 200 `{user:{id,email,role}}` | `me`; identity lookup after login |
| POST `/api/patients` | Bearer patient; JSON `{}` | 201 `{patient:{id,owner_user_id}}` | `create_patient`; `createPatientService.createProfile` |
| GET `/api/patients/me` | Bearer patient | 200 `{patient:{id,owner_user_id}}`; 404 if absent | `my_patient`; `getProfile` maps 404 to null |
| GET `/api/patients/:patient_id` | Bearer owner | 200 `{patient:{id,owner_user_id}}` | `get_patient`; no direct current UI service method |
| POST `/api/patients/:patient_id/assessments` | Bearer owner; `{inputs:{all 12 exact keys},notes?: string|null}`; JSON, 16 KiB cap | 201 `{assessment:A}` | `create_assessment`; `createAssessment` |
| GET `/api/patients/:patient_id/assessments` | Bearer owner; optional single `limit` (1–100, default 20), `after_id` (0–2147483647, default 0); no extra query keys | 200 `{assessments:[A],next_after_id: integer|null}` in ascending ID order | `list_assessments`; `getHistory` requests limit=20 |
| GET `/api/patients/:patient_id/assessments/:assessment_id` | Bearer owner; nested assessment must belong to patient | 200 `{assessment:A}` | `get_assessment`; `getAssessment` |

`A = {id, patient_id, recorded_by_user_id, created_at, inputs, notes}`. Timestamp is server `isoformat()` with no explicit timezone contract; current screens display server time without conversion. IDs/actor/time are server-owned. No `status`, `review_state`, `prediction`, `prescription`, `report` or grant field is returned. No appointment/receptionist/review/prediction/report/admin endpoints exist.

`assessment_payload` rejects missing/extra/renamed inputs, duplicate JSON keys, malformed/non-object JSON, nonfinite numbers, booleans as numbers and server-owned fields. Categorical values are nonblank text up to 256 characters; numeric values are finite int/float with no invented medical ranges. Notes allow null or text up to 4096 characters. It preserves supplied text and explicit zero. This does not validate fitted categorical vocabulary or clinical suitability. `prepareAssessment` turns entered numeric strings into finite JSON numbers; `createPatientService` validates successful response shapes and preserves legacy null inputs.

HTTP failures retain `{error:{code,message}}` via `register_error_handlers`; 401 adds `WWW-Authenticate: Bearer`. Auth and patient responses use `Cache-Control: no-store`. Missing/invalid auth returns 401; wrong known role 403; owner-scoped missing/inaccessible IDs 404; malformed input 400; duplicate account/profile 409; oversized body 413; unavailable auth/database 503. The frontend maps these to safe copy, with patient-specific overrides. Unknown method/path remains 405/404 rather than evidence that an authorization workflow exists.

## Exact V17 boundary

Confirmed by read-only source declarations at `ml/source/AyurSage_Training_v17.py:200–231`, mirrored in `backend/app/api/assessment_validation.py::{CATEGORICAL_INPUTS,NUMERIC_INPUTS,INPUT_FEATURES,OUTPUT_TARGETS}` and `frontend/src/patient/assessmentFields.js`. Order and spelling:

| # | Input name | Current request type |
| --- | --- | --- |
| 1 | `Disease` | Nonblank string |
| 2 | `Symptom Severity` | Nonblank string |
| 3 | `Nadi Reading` | Nonblank string |
| 4 | `Constitution/Prakriti` | Nonblank string |
| 5 | `Stress Levels` | Nonblank string |
| 6 | `Sleep Patterns` | Nonblank string |
| 7 | `Age Group` | Nonblank string |
| 8 | `Physical Activity Levels` | Nonblank string |
| 9 | `BP Systolic` | Finite number |
| 10 | `BP Diastolic` | Finite number |
| 11 | `Pulse Rate` | Finite number |
| 12 | `Weight (kg)` | Finite number |

The four model outputs, in declared order, are `Herbal Therapy Strategy`, `Lifestyle Recommendations`, `Therapeutic Yoga Module`, `Follow-up Recommendation`. **Doctor Prescription & Care Notes** is a separate doctor-controlled manual field, not an input or fifth prediction output. Source `predict_single` (line 2846; placeholder at 2976) returns `PENDING_DOCTOR_REVIEW` in that slot. No backend model/API/frontend editor currently implements the manual field; patient `ClinicalAssessment.notes` cannot be repurposed as it.

Source `make_preprocessor` (1351) uses fitted one-hot categorical encoding with unknowns ignored and numeric passthrough. `predict_single` transforms and decodes four classifiers but also silently defaults missing/invalid input, supplies fallback recommendations, swallows probability errors and adds enrichment/reasoning/diet. Whole-module import brings training/plotting imports and global side effects; its main entry point trains. Future serving must use a reviewed raw four-label adapter with strict input/bundle checks and approved vocabulary/parity, without importing/executing training source or adopting enrichment/defaults implicitly. Source expectations do not prove actual serialized bundle contents.

## Blockers and evidence limits

### V17 loading

`ml/inference/audit.py::run_audit` verifies immutable buffers and refuses a loading request with `LoadingDisabled`; no deserializer, inference callable or enable switch exists. `ml/inference/checksums.py::{APPROVED_ARTIFACTS,VerifiedArtifact,read_verified_file,verify_workspace_buffers}` establish file identity and a same-buffer boundary only.

Historical Phase 2A identity evidence: model 13,023,934 bytes, SHA-256 `e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98`; source 190,567 bytes, SHA-256 `afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3`. Not rehashed in this reconciliation. The artifact README claiming no bundled model is stale. The architecture overview's “unverified names” wording is also stale: declaration names were inspected; runtime preprocessing/bundle compatibility remains unverified.

`docs/setup/phase-2a-v17-compatibility-review.md` and `phase-2b-readiness.md` record absent ML packages, no approved complete runtime lock, historical metadata not bound to this model, unknown actual fitted object graph/vocabulary, absent approved synthetic reference labels and unresolved dataset provenance. Historical package candidates are not approved pins. No clinical performance/production compatibility claim follows from checksums.

`docs/setup/v17-loading-audit.md` (current Step 1.3.5 section) and `verification.md` retain **Step 1.3 NOT ACCEPTED**. A surviving external observer with exact parent/child identity and Docker-to-WSL PID mapping is unvalidated; disappearance/container stopped-state is insufficient. Independent coordinator/daemon-failure recovery and unconditional hard deadlines remain unverified. `reports/step-1-3-5-beeaf978742c/verification-results.json` explicitly marks live worker/full watchdog tests skipped, acceptance false and model_loaded false. `reports/step-1-3-1/evidence-review.json` includes mixed historical scenario results; it does not supersede the current rejection. `worker_diagnostic_audit.py::observe_container_exit` establishes container-level evidence only; `worker_diagnostics.py::classify_tracked_termination` validates supplied evidence, not a surviving collector.

Loading stays deferred. Any future runtime preparation, harmless boundary validation, load/structure attempt and parity execution requires its own approved scope and accepted prerequisites. This reconciliation neither changes controls nor repeats those audit cycles.

### Authentication error and current browser uncertainty

The earlier reported browser message is **“The authentication service is unavailable. Please try again later.”** Its exact source is the 503 mapping in `frontend/src/services/api.js`; `AuthPage.submit` catches the failure and renders `error` in `role="alert"`. `docs/setup/authentication-failure-fix.md` and `authentication-runtime-repair.md` traced live 503 to a standard backend launched without DATABASE_URL/JWT_SECRET_KEY: `require_auth_configuration` rejected before credential validation/database/JWT work. Health 200 did not establish readiness. Those reports record subsequent local-launcher HTTP success and explicitly leave mounted browser interaction unverified.

Fresh read-only GET observations during this reconciliation:

| Request | Observed status |
| --- | --- |
| `http://localhost:5174/api/auth/me` without bearer | 401 |
| `http://127.0.0.1:5000/api/auth/me` without bearer | 401 |
| `http://localhost:5174/api/health` | 200, `{"status":"ok"}` |

These confirm the probed proxy/backend now reach the unauthenticated denial path rather than the old configuration 503. They do not prove successful credentials or readiness for every authenticated database operation. The PowerShell error-response reader returned no 401 body; JSON 401 format is supported by inspected handlers/tests, not a captured body in these probes.

Existing `.local/auth/backend.stderr.log` tail contains login 401s, registration 201, then login 200, `/auth/me` 200 and patient/assessment operations on 13 October. It supports recent mixed login outcomes, but cannot identify the user's account or prove browser rendering. Public login 401 maps to **“Email or password is incorrect.”** Authenticated 401 instead maps to session invalidation. Neither message is asserted to be currently visible: no live browser state, screenshot, credential submission or mounted UI inspection was available/performed in this task. Current visible error, current account credentials/hash, browser event/navigation behavior, live MySQL and production setup remain unverified. Do not reopen the already diagnosed 503 audit without fresh evidence of recurrence.

Historical verification: `authentication-runtime-repair.md` records 97 backend tests and 36 frontend tests passing, build success, and opt-in `frontend/tests/live/auth.test.js` passing after repair. Its named live test creates a synthetic account, so it was deliberately not rerun for this read-only task. Current review/patient test sources were inspected; historical counts are not a claim that every current suite was executed now.

## Dependency-ordered implementation plan

1. **Implement the four-role authorization/provisioning foundation next.** Add receptionist through a new migration (do not rewrite 0001), update existing role constants/CLI choice/frontend labels and route maps coherently, and define explicit administrative/clinical permission scopes, patient–doctor grants, revocation/expiry, grant issuance/delegation and audit events. Preserve owner checks and default clinical denial. Add authorized provisioning/role/grant operations using the existing Flask/auth/account infrastructure; no second auth system. Acceptance covers all four roles, public role injection, absent/revoked/expired grants, cross-patient IDs and admin/receptionist clinical denial before data access. Adapt existing three-role tests and add focused grant/audit tests once.
2. **Build administrative registration and appointment/check-in workflow on that policy.** Extend the existing Patient entity only for approved profile fields; reuse account creation and ownership semantics. Add appointment and attendance entities/services, narrow receptionist responses and scheduling/conflict/status tests. Add a receptionist workspace to existing Router/AppShell/AuthProvider and extend the existing admin home for supported operations. Do not create an alternative patient registration/profile model or expose assessment data through scheduling responses.
3. **Enable granted doctor assessment review with explicit workflow policy.** Extend the existing doctor home to an authorized worklist/detail view, reuse assessment presentation, and extend existing `AssessmentReview` rather than create another review table. Define what assessment approval means before predictions exist; do not imply treatment approval. Implement transactional ordered/concurrent append, actor attribution, immutability, correction/resubmission rules and a separate manual care-notes record/field. Replace the current write blocker only within an explicit authorized service boundary. Extend existing assessment detail/history with serialized status where authorized. Test absent grants, revocation, concurrent append and non-doctor writes.
4. **Resolve the deferred ML gates as one bounded workstream when separately authorized.** Obtain artifact-bound runtime/vocabulary/reference evidence, review the execution boundary and validate missing observer/recovery/deadline prerequisites with harmless fixtures. Only accepted prerequisites permit one authorized load/structure attempt, then approved parity. Reuse checksum/buffer/control evidence; rerun only failed or changed gates. Never duplicate the loader, replace artifacts, invent locks, import training source or repeatedly run full watchdog audits without the missing observer prerequisite.
5. **Integrate predictions after both policy and ML acceptance.** Add assessment-linked run/result persistence, immutable input/provenance snapshots and retry/idempotency/failure semantics. Add one authorized Flask orchestration/adapter path, test denials before model invocation and preserve the exact four-output contract. Link doctor review/care decisions to the result version; define patient-release permissions explicitly. Extend existing doctor/patient screens rather than add another assessment workflow.
6. **Add authorized release/report generation and operations.** Create one report/release lifecycle and protected retrieval path with audited access, versioned reviewed content and storage failure handling. Extend patient details/results/reports and admin audit/operations views. Perform focused end-to-end acceptance for registration → scheduling/check-in → grant → assessment → accepted inference → doctor decision/manual notes → authorized patient report. Production MySQL/storage/deployment checks follow their own concrete configuration changes.

Steps 2–3 can proceed while V17 remains deferred; neither depends on bypassing ML controls. Step 5 depends on grants, review/release policy and accepted loading/parity. Use this document as the shared implementation map, and update its changed rows after each completed slice instead of creating repeated architecture audits or parallel competing pages/APIs/models. The immediate recommended task is step 1, scoped to four-role authorization, controlled provisioning, explicit grants and audit foundations; no prediction endpoint or model execution is part of that task.
