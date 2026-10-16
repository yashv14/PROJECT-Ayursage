# Approved clinical PDF reports

16 October 2026. Extends the existing clinical-review workflow in React/Flask and
SQLAlchemy. No inference, model execution, observer or security-policy change.

## Issuance and release policy

A current, explicitly review-enabled doctor grant is required on every doctor
availability, issuance, link and content request. Existing owner-link, exact
30-day duration, scope, consent, expiry and revocation checks are reused.
Read-only grants, appointments and administrator role do not authorize reports.
Patients may retrieve only their own issued reports; ownership never permits
issuance. Revoking a doctor's grant does not remove the patient's own access to
their issued document. Subsequent doctor requests are denied, including requests
using links signed before revocation. Previously downloaded bytes cannot be recalled.

The authoritative contiguous review history must end in approved. The doctor
explicitly issues that approved content for patient access. Issuance locks the
grant and assessment using the existing review lock order, detaches the snapshot,
renders/uploads the PDF, then commits metadata. Approval identity and timestamp
refer to the saved decision, not necessarily the issuing doctor.

Exactly one report, version 1, is permitted per assessment/approval. Approval is
already terminal. Repeated issuance returns the same metadata/object (HTTP 200),
never regenerates or overwrites it. First issuance returns 201. No regeneration,
in-place revision, correction/replacement or deletion API is introduced. A future
correction policy needs a separate explicit design/migration. Later changes to an
assessment do not change the issued bytes. ORM/bulk report mutation is blocked;
these application guards do not provide database-administrator tamper resistance.

PDF includes available identifiers, assessment inputs/notes, approved clinical
notes, recommendations and provenance, human prescription, review revisions,
approval actor/time, issuance time, version and disclaimer. Earlier prescription
content is identified as earlier content, not the active approved prescription.
No diagnoses, missing fields or ML outputs are invented. Legacy review provenance
remains unclassified. Text is XML-escaped; the bundled Vera font is embedded.
Unsupported characters fail generation rather than silently substituting glyphs.
Additional language/font coverage remains a future deployment requirement.

## API

All paths below are under `/api/patients/{patient_id}/assessments/{assessment_id}`.
JWT authentication and server authorization are required on every request.
All responses use Cache-Control: no-store. Query parameters are rejected.

| Method/path | Contract |
| --- | --- |
| GET `/report` | status: awaiting_approval, not_issued or available; can_generate; report metadata or null. Missing/corrupt storage returns 503, never available |
| POST `/report` | Doctor only, exact JSON `{}`. 409 before approval; 201 first issuance; 200 idempotent retrieval |
| POST `/report/download-link` | Exact JSON `{}`. Returns resource-relative signed URL and expires_in: 900, or 404 if no issued approved report |
| GET `/report/content` | JWT plus X-Report-Link header. Returns application/pdf attachment after identity, authorization, signature age and integrity checks |

The link has a URL fragment carrying a timestamped signature, bound to user,
report ID and PDF digest using a separate signing key/salt. The frontend verifies
the exact same-resource path and 900-second expiry, removes the fragment, and
transmits the capability only in X-Report-Link. This is an **application-mediated
signed download**, not a provider presigned public object URL. Pasting the link
into a new tab is insufficient; the authenticated client consumes it. Tokenless,
tampered, expired or transferred links return 403; the UI clears report state and
offers refresh. A fresh download action obtains a fresh link. Doctor denial also
revalidates the assessment, clearing stale clinical content. Focus/visibility and
unmount invalidate pending report responses. Blob URLs are revoked after delivery.

Signature acceptance is bounded by itsdangerous max_age=900 (integer seconds;
age 900 accepted, age 901 rejected). URLs/tokens are never stored in database or
frontend state. Standard access logs see only the content endpoint path.

## Private storage and deployment prerequisites

No production storage is configured or silently selected. A deployment must
explicitly install an implementation of PrivateReportStorage in
`app.extensions['report_storage']` through trusted application bootstrap, and
provide a separate random REPORT_SIGNING_KEY (at least 32 characters, secret
managed). There is no public configuration endpoint, credential default or model
loading change. Absent storage/signing configuration fails issuance/retrieval 503.

The provider-neutral put/get/delete contract requires private ACLs, create-only
opaque keys, idempotent deletion, bounded network I/O and bytes on reads. Before
production: choose/review provider and adapter, credentials/least privilege,
encryption, retention/backups, maximum document size, timeouts, monitoring,
orphan reconciliation and key rotation. Preserve redaction of Authorization,
X-Report-Link, URL fragments and request/response bodies in proxy/APM tooling.
No object URL, key or storage credentials are exposed in public report metadata.

MemoryReportStorage is an explicitly injected disposable local/test adapter;
private objects exist only in its process dictionary, never a web directory or
relational blob. It is not durable, not a production provider, and not enabled
automatically by TESTING/DEBUG or normal startup. Restarting it loses test PDFs.

## Metadata, failures and recovery

Migration 0008_clinical_reports follows 0007_clinical_review. It adds only
clinical_reports: assessment/review/issuer foreign keys, unique assessment and
review references, version constrained to 1, random object key, PDF SHA-256,
snapshot SHA-256, positive byte length and UTC issuance time. The review reference
links approval identity/time. No PDF bytes or clinical-content duplicate is stored
in the table. No pending status is required: a row is committed only after upload;
availability checks the current approval and object digest/length. No backfill.

Renderer errors create nothing. Failed/partial uploads and precommit database
failures roll back metadata and attempt deletion of this request's exact random
key. Cleanup failure logs a generic reconciliation event and opaque key, never
clinical content/provider exceptions. A lost commit acknowledgement triggers a
fresh metadata lookup: preserve the PDF when committed, delete only when absence
is confirmed, retain for reconciliation if DB outcome cannot be established.
Retry safely returns an existing committed report or issues a new one after failure.
Signing/read failures never delete a previously issued document.

Process death and failed cleanup can leave orphan objects. A production operator
must reconcile provider keys against committed clinical_reports.object_key after
excluding active/in-flight operations and resolving ambiguous commits; do not
blindly delete objects or issued metadata. No background service is added here.
Downgrade drops metadata only and requires separate object reconciliation; it
does not delete private objects. No existing development/production DB was migrated.

## Actual verification for this feature

- Backend related suite: **139 passed**, 37.947s, disposable SQLite. Includes 12
  report tests plus 127 existing regressions. Initial sandbox run had two errors
  opening temporary file-backed SQLite databases (WinError 5); identical elevated
  run passed. No application change was made for those permission errors.
- Final focused report run after additional layout/boundary checks: **12 passed**.
  Covers actual ReportLab bytes and stored fields, approvals, patient boundaries,
  read-only/revoked/role denial, signature expiry/transfer/tampering, integrity,
  idempotence, immutable metadata, upload/PDF/DB/signing failures, cleanup failure,
  lost commit acknowledgement, logging redaction, migration roundtrip/schema match,
  long escaped text and explicit rejection of unsupported glyphs.
- Frontend state/service/route regressions: **67 passed**; render/reception tests
  **3 + 4 + 3 + 5 + 13 + 3 passed** individually, **98 total** excluding browser.
- Production Vite build write:false: **PASS**, 45 modules, 256ms, no dist written.
- Installed Chrome **155.0.8059.40** with existing playwright-core, disposable
  SQLite/Flask at migration head 0008: **8 stages / 9 Node tests passed**, 13.231s
  on the final scenario run after the layout refinement. Actual JWT/HTTP
  authorization, no mocks. Earlier 13.162s and 17.563s runs also passed.
  Report mode explicitly injects private
  disposable storage and random signing key; it does not configure production.
- Browser stages: patient grant; directory/history/detail; unrelated role denial;
  read-only review/report denial; preapproval report rejection and manual review;
  reload/revision/approval history; report issuance/reload and byte-identical doctor
  and owner downloads; revocation with fresh denial and cleared doctor content.
- Synthetic two-page output rendered using existing Windows.Data.Pdf and visually
  inspected. First rendering helper had an AsTask overload error; using the exact
  reflected IAsyncAction overload succeeded without installing tooling. Prescription
  grouping was refined to keep the complete prescription together. Generated PDFs
  and PNGs are ignored under reports/ and are synthetic verification resources.

Commands (root):

```powershell
.venv/Scripts/python.exe -m pip install --dry-run --only-binary=:all: --disable-pip-version-check reportlab==5.0.1
.venv/Scripts/python.exe -m pip install --only-binary=:all: --disable-pip-version-check reportlab==5.0.1 pillow==12.3.0 charset-normalizer==3.5.2
.venv/Scripts/python.exe -m pip check
@'
import sys,unittest
sys.path.insert(0,'tests/backend')
names=['test_clinical_reports','test_clinical_reviews','test_reviews','test_access_grants','test_doctor_directory','test_patients','test_reception','test_assessment_prediction','test_foundation','test_database','test_v17_startup_safety']
r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(not r.wasSuccessful())
'@ | .venv/Scripts/python.exe -B -
```

ReportLab **5.0.1**, Pillow **12.3.0**, charset-normalizer **3.5.2** were installed
only into the confirmed project .venv and pinned in backend requirements. No
existing distribution was upgraded; pip check passed. ReportLab is declared in
requirements.in; requirements.txt includes the two resolved transitive pins.

Commands (frontend/):

```powershell
node --test --test-isolation=none tests/clinical-reports.test.js tests/clinical-review.test.js tests/admin-grants.test.js tests/doctor.test.js tests/patient.test.js tests/foundation.test.js tests/assessment-prediction.test.js tests/session.test.js
# Run each rendering file separately with the same node flags:
# clinical-reports-render, clinical-review-render, admin-grants-render,
# doctor-render, patient-render, reception (all .test.js).
node --input-type=module -e "import { build } from 'vite'; await build({ build: { write: false } });"
$env:AYURSAGE_E2E_DATABASE='sqlite'
$env:AYURSAGE_E2E_REPORTS='1'
$env:AYURSAGE_PLAYWRIGHT_MODULE='C:\Users\yvasa\Videos\AYURSAGE\.phase9-release\frontend\node_modules\playwright-core\index.mjs'
node --test --test-isolation=none tests/e2e/doctor-access.test.js
```

Report mode extends the existing clinical/browser stages; ordinary clinical mode
still requires disposable MySQL. All E2E modes now expect migration head 0008.
Browser/Vite/owned backend are closed at teardown; SQLite/test objects are ephemeral.
No model execution, permanent service, production credentials or package tooling
installation occurred. Existing mocked prediction regression tests do not establish
inference. Frozen model/source SHA-256 still match their recorded identities.

Not verified: new migration/concurrency on live MySQL, cloud storage, production
deployment, other browsers, full language/font coverage or exhaustive races.
V17 runtime/provenance, independent execution-safety and prediction-parity gates
remain blocked and separate. Existing unrelated investigation changes are preserved.

## Exact feature files

New:
- backend/app/api/clinical_reports.py
- backend/app/models/report.py
- backend/app/services/clinical_pdf.py
- backend/app/services/report_storage.py
- backend/migrations/versions/0008_clinical_reports.py
- frontend/src/services/reports.js
- frontend/src/pages/ClinicalReportPanel.jsx
- tests/backend/test_clinical_reports.py
- frontend/tests/clinical-reports.test.js
- frontend/tests/clinical-reports-render.test.js
- docs/setup/clinical-pdf-reports.md

Updated:
- backend/app/api/__init__.py
- backend/app/models/__init__.py
- backend/config/__init__.py (report secret only; V17 policy unchanged)
- backend/requirements.in
- backend/requirements.txt
- frontend/src/auth/AuthContext.jsx
- frontend/src/pages/AssessmentDetailPage.jsx
- frontend/src/pages/DoctorReviewPanel.jsx
- frontend/src/pages/PatientWorkspacePage.jsx
- frontend/src/services/api.js
- frontend/tests/e2e/doctor-access.test.js
- frontend/tests/flask_auth_fixture.py
- tests/backend/test_foundation.py
- docs/architecture/ayursage-system-map.md
