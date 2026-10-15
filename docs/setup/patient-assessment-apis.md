# Patient Management and Clinical Assessment APIs - 13 October 2026 (Asia/Calcutta)

## V17 integration update - 14 October 2026 (Asia/Calcutta)

Static implementation only: no Python execution, imports, tests, startup, model
deserialization, inference or package installation was performed. The original
milestone below is historical. The existing frontend still saves assessments
without requesting predictions; its architecture and workflows are unchanged.

`POST /api/patients/{patient_id}/assessments` retains bearer authentication,
patient role and owner checks. Its JSON envelope now accepts exactly `inputs`,
optional `notes` and optional boolean `predict` (default false). The 12 exact
input keys and types listed below are unchanged. Notes remain optional/null or a
string up to 4096 characters; the request cap remains 16 KiB. Duplicate keys,
unexpected keys, invalid types and nonfinite numbers are rejected.

- Omitted/false `predict`: existing 201 `{assessment: ...}` save behavior.
- True `predict`: validate inputs, call the already-loaded service, then persist
  the assessment through the same lifecycle. Any model failure precedes the DB
  write. A DB failure returns the existing error/rollback behavior and never
  returns a successful prediction response.
- Successful 201 additionally contains `prediction` with
  `model_version: "AyurSage_v17"`, `status: "pending_clinical_review"`,
  `persisted: false`, and `outputs`. Outputs has exactly four string-valued keys:
  `Herbal Therapy Strategy`, `Lifestyle Recommendations`,
  `Therapeutic Yoga Module`, `Follow-up Recommendation`.

Only inputs and notes are persisted. The current schema has no prediction result
storage; labels are response-only and are absent from subsequent history/detail
reads. No labels are inserted into notes, inputs or review history. This status
marks the returned suggestions, not a durable clinical decision. Prescription
decisions remain under doctor control; this API grants no approval capability.

Validation errors return 400 `{error: {code: 400, reason: "invalid_assessment",
message: <safe contract explanation>}}`. Fitted-vocabulary rejection uses 400
and `reason: "invalid_model_input"`. Missing/unloaded/disabled or incompatible
models return 503 and `reason: "model_unavailable"`; transform/predict/decode
failures return 500 and `reason: "inference_error"`. Model messages state that no
prediction or assessment was saved. Malformed JSON/content type retains generic
400; size failures retain 413. Existing 401/403/404 ownership semantics and
Cache-Control: no-store remain. Responses expose no exceptions, patient values
in diagnostics, internal objects, paths or loading controls.

`backend/app/services/v17.py` constructs an unloaded, app-scoped service.
`V17_MODEL_LOADING_ENABLED` is explicitly false in backend configuration and is
not an environment or HTTP switch. A separately authorized internal bootstrap
must provide a true configuration value at application creation and explicitly
call the service's `load()` in an approved runtime. Changing configuration alone
does not load anything. No such bootstrap was executed or added to startup.
The loader uses the existing `ml/inference/checksums.py` fixed path/approved
SHA-256 checks for model and source, then joblib-deserializes the same immutable
verified model buffer. It never imports the training source or reopens the model.
Runtime imports are inside this boundary; no dependency manifests changed.
Checksum validation is an identity check, not process isolation or compatibility
approval. Loader failures/warnings leave the service unloaded.

Static source evidence: `make_preprocessor` defines categorical OHE named `cat`
with unknowns ignored and numeric passthrough named `num`. `predict_single` steps
1-3 build a named DataFrame, transform once, select
`models[target][best_overall_model]`, predict four times and decode via
`le_output[target].inverse_transform`. The bundle is not a single estimator
with a top-level predict interface. The adapter implements only these raw-label
steps and requires matching ordered feature/target metadata, fitted categories
and output encoders. It preserves categorical spelling/case/whitespace and
rejects values outside fitted `categories_` before transformation. It does not
use training normalization maps, zero/default replacements, probability calls,
fallback outputs, enrichment, diet, random reasoning or prescription placeholders.

Concrete differences from the full source function: strict validation replaces
its missing-input/numeric coercion and unknown-category tolerance; raw decoded
strings replace its enriched section dictionaries. These are intentional API
constraints. Actual frozen bundle structure/vocabulary, installed runtime and
raw-label parity remain unverified; mismatches fail unavailable rather than
repairing/refitting or assuming an algorithm. Result persistence stops at the
current schema boundary; a future approved schema/lifecycle change is needed if
durable prediction storage is required.

Before separately authorized runtime validation: establish the compatible ML
runtime/dependency evidence and approved bounded loading environment; validate
bundle structure and fitted vocabulary against the frozen identities; compare
four decoded labels with authorized synthetic reference cases; check malformed
and unknown inputs, warnings, transform/predict/decode failures, disabled loading,
authentication/ownership, transaction failures and unchanged save-only behavior.
No live enablement or prediction success is claimed by this static change.

## Original assessment API milestone

This milestone reuses the existing Flask factory/API blueprint, SQLAlchemy models,
database configuration and JWT/role/ownership helpers. No dependencies changed.
No inference, enrichment, doctor approval, reports, frontend, Docker or deployment
work was performed. Watchdog Step 1.3 remains deferred and NOT ACCEPTED.

## Inspection and authorization decision

Read the models, all prior migrations, Alembic environment, database extension,
factory, configuration, authentication code, helpers, backend tests and
authentication.md. The Patient model supports only id/owner_user_id. Registration
already creates that profile. ClinicalAssessment supports patient/recording-user
links, creation time and manual notes, but lacked input storage. No doctor assignment
or access-grant model exists.

The user explicitly selected: keep doctor access denied until explicit grants are
implemented. Therefore every new route authenticates and requires the patient role.
Reads and assessment writes filter by authenticated owner and invoke the existing
ownership helper. Doctors and administrators receive generic 403 on all these
routes; administrator status has no automatic bypass. Changing patient IDs cannot
read/create records for another owner. Cross-owner and nonexistent IDs both return
404, including nested assessment IDs belonging to another patient. Missing/invalid
bearer tokens receive 401 when auth is configured; unavailable configuration or
database receives 503 as in the auth milestone.

## Routes

All successful resource responses use `{patient: ...}`, `{assessment: ...}` or
`{assessments: [...], next_after_id: ...}`. JSON keys are quoted normally on the wire.
Errors reuse `{error: {code, message}}`, with generic messages. All responses from
the patient blueprint use Cache-Control: no-store. No account passwords, hashes,
JWTs, emails or model outputs appear in resource responses.

| Method / path | Request and behavior |
| --- | --- |
| POST /api/patients | JSON `{}` only; creates a profile for the authenticated patient without one; 201. Existing profile or concurrent duplicate: 409 |
| GET /api/patients/me | Retrieves own profile; 200 or 404 if absent |
| GET /api/patients/{patient_id} | Retrieves owned profile; 200 or 404 |
| POST /api/patients/{patient_id}/assessments | Required inputs object, optional notes; 201 linked assessment, authenticated actor recorded |
| GET /api/patients/{patient_id}/assessments | Owned history ordered by id; limit defaults to 20, allowed 1-100; after_id defaults to 0; next_after_id is null at the end |
| GET /api/patients/{patient_id}/assessments/{assessment_id} | Owned assessment under its actual patient; 200 or 404 |

Profile responses contain only id and owner_user_id. No demographics were invented.
Most newly registered patients already have a profile, so they retrieve it rather
than create another. POST supports legacy/provisioned patient accounts without a
profile. Caller-supplied owner IDs, account roles, demographics and unknown fields
are rejected, not silently discarded. No update/delete operations were added.
URL resource IDs are bounded to the existing MySQL signed INTEGER schema; invalid
or oversized IDs receive 404 before database binding. Invalid pagination values,
unknown parameters or repeated query keys receive 400.

Assessment responses contain id, patient_id, recorded_by_user_id, created_at,
inputs and notes. The recording actor is always the verified user, never a request
field. Timestamps retain existing database-clock semantics; no UTC conversion is
claimed. Notes entered through these owner-only APIs are patient-supplied records,
not doctor-approved clinical decisions.

## Exact V17 contract and structural validation

Read only the frozen source feature/output declarations and example, without
importing/executing training source or loading any artifact. The new validation
constants exactly match those source declarations. A focused test parses the
source with ast and compares literal declarations without executing code.

Required input keys, unchanged:

1. Disease
2. Symptom Severity
3. Nadi Reading
4. Constitution/Prakriti
5. Stress Levels
6. Sleep Patterns
7. Age Group
8. Physical Activity Levels
9. BP Systolic
10. BP Diastolic
11. Pulse Rate
12. Weight (kg)

The first eight must be nonblank strings; the last four must be finite JSON
numbers. Booleans, numeric strings, nulls, NaN/infinities, nested values and missing,
extra or renamed keys are rejected. All twelve are required on API creation.
Supplied values are preserved without trimming, encoding or replacing missing
values with zero. An explicitly supplied zero is stored as zero, without claiming
it is medically valid. No categorical domain, clinical range, preprocessing rule,
inference readiness or medical validity is established by these checks.

Payload shape is `{"inputs": {all twelve exact keys}, "notes": optional string or null}`.
Inputs are required; notes may be omitted. IDs, actor, timestamps, outputs and any
other envelope fields are rejected. Duplicate JSON keys, malformed/non-object JSON,
NUL/invalid UTF-8 text and wrong content types produce 400. Nonstandard numeric
constants are rejected. Technical storage/resource caps: 16 KiB request, 256
characters per categorical string, 4096 characters for notes; exceeding request
size produces 413. These are resource limits, not medical ranges.

The four outputs remain Herbal Therapy Strategy, Lifestyle Recommendations,
Therapeutic Yoga Module and Follow-up Recommendation. No output is generated,
accepted in the assessment request, or added to the database. Diet remains separate.
The existing frozen-contract documentation and source declarations are preserved.

## Schema and failure behavior

New migration `0003_assessment_inputs`, following 0002, adds nullable JSON inputs
to the existing clinical_assessments table. Prior migrations are unchanged. The
model uses SQLAlchemy JSON with none_as_null=True, consistent with its official
[JSON type documentation](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON).
Existing assessments keep SQL NULL; no backfill or invented clinical values.
Retrieval explicitly returns inputs:null for such legacy manual records. New API
creation requires a complete object. Downgrade removes stored input objects;
only disposable test databases were downgraded.

No startup auto-migration was introduced. Upgrade the intended database through
the existing environment-based Alembic mechanism before using these APIs:

```powershell
.venv/Scripts/python.exe -B -m alembic -c backend/alembic.ini upgrade head
```

This is an instruction, not an executed CLI/production migration. Tests exercised
upgrade/downgrade/reupgrade with legacy data on SQLite and generated MySQL SQL,
including `ADD COLUMN inputs JSON`; no SQL was applied to live MySQL.

Auth decorators retain safe database-exception handling: rollback, generic 503,
no driver error logging. Profile uniqueness races roll back with generic 409.
Tests verify failed assessment writes leave no rows and the session can be reused.
Validation errors do not echo rejected patient values. Request size limits follow
the existing Flask request mechanism ([official API](https://flask.palletsprojects.com/en/stable/api/#flask.Request.max_content_length)).

## Executed verification

Exact commands, from the workspace root:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

Full-suite commands used approved access for the existing file-based migration
test's temporary directory; new API tests use isolated SQLite and Flask clients.
First run: 77 tests, one error when an oversized patient ID overflowed SQLite
integer binding. Added schema-bound resource-ID guards and tests for assessment
IDs too; text validation also rejects invalid Unicode before database writes.
Final full run: **77 tests in 12.138 seconds, OK, exit 0** (52 existing + 25 new).
pip check: exit 0, `No broken requirements found`. No packages were installed.

Tests cover own-profile creation/retrieval, registration-profile reuse, duplicates,
unique constraints, input structure/types/names, unauthenticated requests, all
doctor/admin role denials, cross-patient access, mismatched nested IDs, persistence,
actor linkage, missing-input/no-default handling, null legacy inputs, pagination,
malformed/duplicate/oversized JSON, rollback and absence of sensitive error logging,
migrations and frozen source contract names. Existing schema-agreement, auth,
health and environment tests also passed. The existing route assertion was updated
for the six new operations; no existing route was removed.

Route inspection exited 0 with ten operations:

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/register
GET  /api/health
POST /api/patients
GET  /api/patients/me
GET  /api/patients/<int:patient_id>
POST /api/patients/<int:patient_id>/assessments
GET  /api/patients/<int:patient_id>/assessments
GET  /api/patients/<int:patient_id>/assessments/<int:assessment_id>
```

Final review used the pre-edit text/hash snapshot because this workspace has no
Git repository. Generated and inspected unified diffs for all six modified existing
files; read the new route, validator and migration files and reviewed the new tests.
The changes match this milestone: one blueprint, one added model column, one new
migration, focused tests and documentation. No duplicate auth/database/factory or
doctor permission bypass was introduced.

The complete inventory comparison found 49 original files: six intentionally
modified, 43 unchanged, five added, none removed. The changed/new list below matches
that comparison. All 18 protected files under ML, infrastructure, ML/integration
tests and frontend manifests are byte-identical. V17 model/source/dataset, loading
controls, watchdog files, previous migrations, authentication code, dependency
files, database configuration and .gitignore remain unchanged. Existing architecture
contract text naming the 12 inputs and four outputs was not edited.

The exact post-edit inventory command was:

```powershell
.venv/Scripts/python.exe -B -c "import hashlib,json,pathlib; roots=['backend','tests/backend','docs','ml','infra','tests/integration','tests/ml','frontend']; paths=[p for root in roots for p in pathlib.Path(root).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','.venv','__pycache__','.npm-cache'))]+[pathlib.Path(x) for x in ['README.md','.env.example','.gitignore']]; print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))"
```

The inventory command exited 0; its hash values were compared with the pre-edit
snapshot. Environments, bytecode and frontend caches were excluded. No Git diff,
tracked-file result or commit is claimed.

## Changed files

Updated:

- backend/app/api/__init__.py
- backend/app/models/__init__.py
- tests/backend/test_foundation.py
- README.md
- docs/architecture/overview.md
- docs/setup/implementation-checklist.md

Added:

- backend/app/api/assessment_validation.py
- backend/app/api/patients.py
- backend/migrations/versions/0003_assessment_inputs.py
- tests/backend/test_patients.py
- docs/setup/patient-assessment-apis.md

## Unresolved limitations and unperformed checks

Doctor grants/assignments and administrator patient-data policy do not exist;
access is explicitly denied as selected by the user. No doctor clinical workflow
is available. Profiles have no demographic fields; only the existing owner link is
managed. Input completeness/type validation is enforced by the API, not by JSON
database shape constraints; direct ORM/SQL writes may still create null or other
JSON values. Legacy records remain incomplete and are never inference-ready by
assumption. No categorical encoding, clinical ranges, preprocessing compatibility,
doctor approval or inference correctness is claimed.

No live MySQL connection/migration/JSON/collation verification, production/cloud
migrations, deployment, Docker, live HTTP server, frontend, ML/loading/inference,
watchdog suites or clean-environment installation was performed. No production
credentials were requested or used. Existing authentication deployment limitations
remain documented in authentication.md. Work stops at this milestone.
