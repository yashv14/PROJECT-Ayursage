# Phase 2A: V17 inference compatibility review

13 October 2026, Asia/Calcutta. **Identity verified; safe loading and inference
compatibility are NOT established. Phase 2B has not begun.** Only this report is
added. No source execution, pickle deserialization, dependency installation,
application edits, Docker changes or watchdog work was performed.

## Verified facts and evidence

The existing verification-only audit read opaque bytes and matched both identities:

| File | Size (bytes) | Approved and measured SHA-256 |
| --- | ---: | --- |
| ml/artifacts/ayursage_model.pkl | 13,023,934 | e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98 |
| ml/source/AyurSage_Training_v17.py | 190,567 | afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3 |

`ml/inference/checksums.py`: `APPROVED_ARTIFACTS`, `read_verified_file`,
`VerifiedArtifact`, `verify_workspace_buffers`. Verification retains immutable
bytes; consumption must use that same buffer, not reopen a verified path.
`ml/inference/audit.py`: `run_audit` and `main` contain no deserializer.
The loading-request branch raises `LoadingDisabled`; there is no enable switch or
environment override. No loading request was made during this review.
Checksums identify the approved bytes, not compatibility or permission to execute
serialized code. `ml/artifacts/README.md` still says no model is bundled; this is
stale documentation, not evidence that the inspected artifact is absent.

**Dependency evidence has three distinct levels:**

| Component | Historical metadata declaration | Older experimental audit report | Current project runtime |
| --- | --- | --- | --- |
| Python / OS | 3.12.7 / Windows | 3.12.7 | 3.12.7 / Windows |
| scikit-learn | 1.9.0 | 1.9.0 | Not installed |
| NumPy | No version recorded | 2.4.6 | Not installed |
| pandas | No version recorded | 3.0.3 | Not installed |
| SciPy | No version recorded | 1.18.0 | Not installed |
| joblib | No version recorded | 1.5.3 | Not installed |
| XGBoost | Available; selected algorithm XGB; no version | 3.3.0 | Not installed |

Read the JSON metadata referenced by the existing loading report at
`C:/Users/yvasa/Downloads/AYUR_mega/AYUR_mega/results/metadata.json`:
pipeline_version=AyurSage_v17, selected_algorithm=XGB; environment additionally
declares CatBoost, SMOTE and SHAP available without versions. Its SHA-256 is
`17f9cbd1e5f61f38195947ebc2ade6facbd8970278262a8ea4bc29efb8aab239`.
It contains no artifact-hash field: **its linkage to this model is unproven**.

The candidate-version column is documented in
`C:/Users/yvasa/Videos/AYURSAGE/docs/phase5-evidence.md` and summarized in
`docs/setup/v17-loading-audit.md` (Dependency plan). That older audit inherited
system packages, used unapproved candidates and changed random-state handling.
Its claimed parity/timing was not rerun here and is not production acceptance or
an original training lock. No versions in that column are proposed as pins.
Current `.venv` has backend dependencies only; `ml/.venv` has no installed
distributions. Both pyvenv.cfg files disable system-site-packages. Neither
backend requirement manifest specifies an ML runtime; no ML lock/metadata file
was found in this workspace. CatBoost, SHAP and imbalanced-learn are also absent.
The source's serving core uses pandas/NumPy and fitted sklearn objects, serialized
with joblib; SciPy and the actual selected estimator's runtime must be resolved.
Historical XGB selection suggests XGBoost, but the pickle's actual class references
remain unknown. Optional training/plotting imports do not justify installing them.

## Source contract, fallback behavior and serving gap

Read-only source evidence in `ml/source/AyurSage_Training_v17.py`:

- Lines 200-231: `CATEGORICAL_COLS`, `NUMERIC_COLS`, `INPUT_FEATURES`, `OUTPUT_TARGETS`.
- `make_preprocessor` (1351): fitted categorical OneHotEncoder with unknowns
  ignored, numeric passthrough, remainder dropped; `normalize_labels` (376) is
  used during training preparation, not called by `predict_single`.
- `train_ayursage` (1968), bundle construction around 2699-2737: source intends
  shared_pre, le_output, ordered feature/target lists and models[target][winner],
  with one selected algorithm for four classifiers. These are source expectations,
  not inspected pickle contents.
- Metadata writer around 2786-2807 records only Python/sklearn versions and
  availability flags; it cannot recover the missing original package versions.
- `predict_single` (2846): constructs a DataFrame, transforms with shared_pre,
  predicts each target separately and inverse-transforms its encoded label.
  Thus it is designed to accept the twelve named fields and produce four ML
  labels; success with this artifact/runtime has NOT been demonstrated.

Exact categorical keys: Disease; Symptom Severity; Nadi Reading;
Constitution/Prakriti; Stress Levels; Sleep Patterns; Age Group; Physical Activity
Levels. Exact numeric keys: BP Systolic; BP Diastolic; Pulse Rate; Weight (kg).
Exact outputs: Herbal Therapy Strategy; Lifestyle Recommendations; Therapeutic
Yoga Module; Follow-up Recommendation. No fifth ML output is authorized.

Silent behaviors that must not pass into a prediction API unchecked:

- `predict_single` lines 2868-2872 uses input_data.get(feature, 'Unknown'), then
  numeric errors='coerce' and fillna(0.0). Missing/bad numbers can become zero;
  missing categories become Unknown. Extra input keys are ignored.
- Unknown categories can become all-zero one-hot blocks. The current API permits
  nonblank strings but has no fitted-vocabulary validation. Case/whitespace and
  training normalization parity require an explicit policy; do not invent aliases.
- Missing target labels receive default recommendation categories (2916-2919).
  Missing engine entries also receive fallback detail; probability exceptions
  silently become confidence=None. An incomplete bundle must fail, not manufacture
  successful recommendations.
- `_extract_wellness_factors` (3036; defaults around 3064-3071) substitutes
  120/80/70/75 for missing or unparseable BP/weight/pulse. These are source
  fallbacks, NOT approved clinical defaults. `generate_clinical_reasoning` (3390;
  random.seed at 3418) modifies global random state.

The full `predict_single` returns enriched lifestyle/yoga/diet/reasoning/confidence
sections plus Doctor Prescription & Care Notes=PENDING_DOCTOR_REVIEW. That slot
is manual workflow metadata, not an ML output or authorization control. This full
function therefore exceeds a four-label inference-only milestone. Its enrichment
must not be quietly integrated. Whole-module import also changes warning/logging
configuration and imports training/plotting packages; the main entry point trains
and runs a demo. Neither path was executed.

## Current API/schema fit and blockers

`backend/app/api/assessment_validation.py`: `assessment_payload` requires exactly
the twelve keys, eight nonblank strings and four finite numbers; rejects missing,
renamed, extra, boolean/nonfinite and malformed values. It preserves supplied
values and invents no medical ranges. These are structural checks, not categorical
domain/preprocessing approval. Inference must revalidate stored records too:
direct ORM/SQL writes bypass this validator.

`backend/app/models/__init__.py`: ClinicalAssessment stores patient_id,
recorded_by_user_id, created_at, notes and nullable inputs. Migration
`0003_assessment_inputs.py` preserves legacy SQL NULL rather than fabricated zeros.
There is no prediction result/version/run-status/review-state persistence schema.
`backend/app/api/patients.py`: owned_patient and all six operations enforce owner
scope. `backend/app/auth/security.py`: auth_required, roles_required and
require_patient_owner provide authentication and denial. Doctors/admins currently
cannot access patient records; no grants exist.

**Loading blocker:** checksum buffers are reusable, but no loader or accepted
bounded execution environment exists here; the ML runtime is absent and original
dependency evidence is incomplete. Step 1.3 remains NOT ACCEPTED and deferred.
This review does not alter its criteria or substitute for isolation/deadline
acceptance. The current scaffold cannot perform a loading test at all. A venv
alone is not an execution security boundary.

**Endpoint blockers:** artifact-bound bundle/vocabulary/class metadata, an approved
runtime lock or explicitly approved experimental runtime, synthetic reference
inputs/expected labels and parity evidence are missing. Existing reports also
record unresolved training-dataset provenance; this review does not select a
dataset or authorize retraining. Patient release/doctor review policy must be
resolved before exposing recommendations: the current owner-only APIs and a
placeholder string do not implement doctor approval. Result persistence and
failure/idempotency semantics also require explicit design.

## Minimal ordered Phase 2B plan (requires separate authorization)

1. Obtain artifact-bound provenance, runtime/package evidence and owner-approved
   synthetic references. If the original lock cannot be recovered, explicitly
   approve an experimental runtime and label it accordingly; fabricate no pins.
2. Review an inference-only dependency lock and a separately authorized bounded
   load/structure protocol: trusted same-buffer load, read-only artifacts, no
   secrets/patient mounts/network, external hard deadline and resource limits,
   safe diagnostics. Stop if isolation/deadline acceptance is unavailable. Do not
   revive or silently bypass the deferred watchdog milestone.
3. Only after authorization/environment preparation, perform one bounded load
   without importing/executing training source. Validate bundle identity/schema,
   fitted transformer/encoders, exact ordered inputs/targets, actual winner and
   classifier classes. Fail on warnings, mismatch or missing components; never
   repair/refit/fall back to another model. Record actual runtime, not guesses.
4. Review a separate serving adapter limited to transform, four predict calls and
   label decoding. Require complete typed inputs and an approved vocabulary/
   normalization policy. Compare those raw labels to source-step semantics and
   approved fixtures; exclude enrichment/reasoning unless separately authorized.
5. Establish prediction authorization, unapproved-result visibility and durable
   assessment-linked provenance/status/idempotency policy before endpoint work.
   Keep doctor/admin denial until explicit grants exist; do not return unreviewed
   recommendations merely because the caller owns an assessment.
6. Implement an endpoint only after load/parity and policy gates pass, with focused
   migration/API tests. No frontend, enrichment, approval workflow or deployment
   is implied by this plan. Stop at any failed gate.

Required tests before acceptance:

- **Loading:** unchanged/missing/corrupt hashes; same verified bytes/no reopen;
  loading disabled by default; imports/training prohibited; structure/version/
  fitted-state failures; compatibility warnings; unavailable runtime; enforced
  timeout, resource/network/write denial and cleanup of the entire worker.
- **Parity:** exact feature/target names/order; approved vocabulary and encoding;
  approved synthetic fixtures bound to model/source/runtime hashes; exact decoded
  four-label results; explicit zero preserved; missing/null/nonfinite/bad types,
  extra keys and unknown categories fail under reviewed policy; repeatability and
  concurrency. No default outputs or enrichment leak. Confidence only if approved.
- **Authorization:** missing/invalid JWT, each role, other patient's assessment,
  mismatched nested IDs, absent grants and unapproved-result visibility; denial
  before invoking model work, with no role escalation or output release bypass.
- **Failures:** missing model, transform/predict/decode errors, deadline/worker
  failure, incomplete/nonfinite outputs and DB errors; generic responses, no
  input/token/result logging, no fake success, no fallback labels, correct rollback.
- **Persistence:** exact immutable input snapshot and assessment/actor linkage;
  artifact/source/runtime provenance and run status; legacy null inputs refused;
  failures cannot create successful results; retries/concurrency follow approved
  idempotency rules; existing assessment reads/ownership remain unchanged.

## Commands and actual outcomes

Read-only inspection used Get-Content/Select-Object and rg on the files/functions
above; no training import, metadata deserialization from pickle or model execution.
Version inspection used importlib.metadata, not imports of ML packages. Historical
JSON was parsed only for version/algorithm/environment evidence, without printing
dataset paths or clinical contents. The current report distinguishes declarations
and historical observations from verified model state.

Executed check commands from the workspace root:

```powershell
ml/.venv/Scripts/python.exe -B -m ml.inference.audit
ml/.venv/Scripts/python.exe -B -c "import unittest; suite=unittest.defaultTestLoader.discover('tests/ml'); excluded={'test_loading_refused_even_after_success','test_bad_source_blocks_loading_request_before_boundary','test_missing_model_blocks_loading_request_before_boundary','test_cli_exit_codes_and_safe_reports'}; tests=[test for group in suite for case in group for test in case if test._testMethodName not in excluded]; result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests)); raise SystemExit(not result.wasSuccessful())"
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
ml/.venv/Scripts/python.exe -B -c "import sys,importlib.metadata as m,json; print(json.dumps({'python':sys.version.split()[0],'distributions':[d.metadata['Name'] for d in m.distributions()]}))"
.venv/Scripts/python.exe -B -c "import sys,importlib.metadata as m,json; names=['numpy','pandas','scipy','scikit-learn','joblib','xgboost','catboost','shap','imbalanced-learn']; installed={d.metadata['Name'].lower():d.version for d in m.distributions()}; print(json.dumps({'python':sys.version.split()[0],'platform':sys.platform,'ml_packages':{n:installed.get(n,'NOT INSTALLED') for n in names}},indent=2))"
```

All exited 0. Audit: CHECKSUMS_VERIFIED_LOADING_DISABLED, all three loading/inference
flags false. Safe ML subset: **13 tests, 0.042 s, OK**. Four tests that request
loading or invoke --load internally were deliberately excluded, not claimed passed.
Backend: **77 tests, 12.510 s, OK**. Tests used approved temporary-fixture access;
no real patient database was touched. pip check: No broken requirements found.
Routes: existing ten operations only; no prediction endpoint. Version observations
are listed above; audit environment distribution list is empty.

Not performed: loading/deserialization, --load invocation, training/source execution,
dependency install/upgrade, actual bundle inspection, prediction/parity, worker/
watchdog/Docker tests, live MySQL, production migrations or deployment. No earlier
audit result is presented as a new successful compatibility test.

Preservation: before/after SHA-256 inventory comparison found **all 54 existing
files unchanged, no removals, exactly this report added**. Inventory covered backend,
tests, docs, ML artifacts/source/dataset/controls, infrastructure and frontend
manifests, plus README.md, .env.example and .gitignore; environments/bytecode/caches
were excluded. No application, dependency manifest, frozen artifact, watchdog or
Docker file changed. No Git repository exists, so no Git diff/commit is claimed.

Exact inventory command, run before and after report creation:

```powershell
.venv/Scripts/python.exe -B -c "import hashlib,json,pathlib; roots=['backend','tests','docs','ml','infra','frontend']; paths=[p for root in roots for p in pathlib.Path(root).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','.venv','__pycache__','.npm-cache'))]+[pathlib.Path(x) for x in ['README.md','.env.example','.gitignore']]; print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))"
```

Both inventories exited 0; their values were compared directly. Stop here: no
Phase 2B authorization, runtime preparation or loading action is implied.
