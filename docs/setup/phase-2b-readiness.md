# Phase 2B readiness: preparation decision

## Producer evidence / existing fixture investigation — 14 October 2026

**Still NOT READY.** New read-only evidence materially strengthens the association
between the frozen artifact and historical training records, and recovers one
complete original-demo candidate. It does not recover a complete producer runtime
or supply owner-approved parity fixtures. This section updates the earlier
"metadata unbound" / "reference predictions absent" findings below: an existing
co-versioned candidate is now located, but its trust/approval and runtime gaps
remain. No reference output was generated in this investigation.

Search roots:

- **W:** current `C:/Users/yvasa/Videos/PROJECT-Ayursage` documentation, manifests,
  ML source, tests and reports.
- **P:** supplied producer project `C:/Users/yvasa/Downloads/AYUR_mega/AYUR_mega`,
  including results, training log, manifests, venv configuration, CatBoost records,
  CI workflow, local Git history, nested Full_Stack_DevOps copy and existing ZIPs.
- **O:** older `C:/Users/yvasa/Videos/AYURSAGE` documentation, audit/parity scripts,
  tests, backend requirements/constraints, ML evidence/reference locations, audit
  venv configuration, CI workflow and local Git history.

No training/inference/package/module execution was used: inspection comprised
Get-Content, rg/file inventories, JSON parsing, literal/AST inspection, read-only
Git commands and bounded reads of existing ZIP entries. Git model blobs and ZIP
model entries were treated solely as opaque bytes for SHA-256 comparison; no
pickle/opcode interpretation or deserialization occurred. Existing W artifact
hashes and serving findings were reused, not re-investigated. Application/patient
databases and secret environment files were not used as reference fixtures.

### Producer records and provenance found

| Evidence location | Direct finding | Limit |
| --- | --- | --- |
| P `results/metadata.json` | AyurSage_v17, selected XGB, Python 3.12.7, sklearn 1.9.0, Windows, seed 42; declared training timestamp `2026-07-22T03:59:48+00:00Z` | No NumPy/pandas/SciPy/joblib/XGBoost versions, native-build/architecture/protocol record or model-hash field. Timestamp is a recorded string with redundant timezone suffix, not independent clock attestation |
| P `op.txt`, lines 328–350 | Recorded production save of four XGB classifiers to ayursage_model.pkl, successful save, then metadata/architecture-summary writes | Does not log artifact/source SHA-256 or full runtime versions |
| P `results/training_results.json`, `results/architecture_summary.md` | Stored unified XGB selection, comparison and per-output aggregate metrics, consistent with log/metadata | Metrics/plots/class distributions are not per-case input/output fixtures or resolved environment exports |
| P `catboost_info/catboost_training.json`, learn_error.tsv, time_left.tsv | Training iterations/timing/metrics; JSON meta parameters empty | No exact package/build record; CatBoost candidate training is not proof of production estimator/runtime |
| P `.venv/pyvenv.cfg` | Declares Python 3.12.7 and system-site-packages=true | Current directory configuration cannot prove which inherited packages produced the July artifact; only pip dist-info is local to that venv |
| Original Git snapshot P `8a76d7ac84f5741cf6649f2d763703348a820a13`, dated 6 August 2026 | Contains model, frozen source, metadata, log and training-results records together. Committed model/source SHA-256 match W's recorded approvals exactly | Strong content association in local Git, not verified producer identity/signature, execution attestation or a complete runtime record |
| P `AyurSage_Full_Stack_DevOps.zip` | Contains the same frozen model/source, metadata, op.txt and current requirements bytes as P | Packaging corroborates association; duplicates are not independent experiments or approval |

The Git comparison was performed on bytes captured from `git show <commit>:<path>`
without executing their content. Model/source bytes match exactly. Metadata,
training-results and log committed/working hashes differ due only to CRLF checkout
conversion; normalized text matches, and both JSON documents parse identically.
This is **not substantive metadata/log drift**. Recorded evidence identities:

| File | Current P bytes / SHA-256 | Original committed SHA-256 |
| --- | --- | --- |
| `results/metadata.json` | 1,284 / `17f9cbd1e5f61f38195947ebc2ade6facbd8970278262a8ea4bc29efb8aab239` | `182f24294b25a5bedd5f9909afb0ea135acab2791d78b93421bf58e318505db6` |
| `op.txt` | 29,914 / `4be2b681ada7fe370db7f1f3982caa2ac518c64536384882649d9a62065da5a5` | `9999397c3dcad67c8b33ab5aeed0a7a79ed56cb1b31f7a2d3fa5b274d780ff23` |
| `results/training_results.json` | 6,607 / `065d191e1f27d3f2870f64ea62efc366887a2cefe3244a584069b3c21e92049c` | `a4626a586659fc01adb0ccd37b4711766beee38dc8c2c7a18af871dbca981f0c` |

The model/source identities in that commit and the ZIP are the already approved
`e0b60420…` / `afc2fb4b…` values listed fully in the previous assessment. These
new-copy checks strengthen provenance association; they do not prove that matching
code ran in the recorded environment or that its pickle can be executed safely.

### Runtime/CI evidence: exact facts versus deployment assumptions

Original committed `requirements.txt` has **ranges**, including joblib>=1.3.0,
numpy>=1.24.0, pandas>=2.0.0, scikit-learn>=1.4.0, xgboost>=1.7.0 and
imbalanced-learn>=0.11.0; it is not a resolved training lock and omits SciPy's version.
P's later/current manifest pins sklearn==1.9.0 with a training-version comment,
but retains ranges for other ML dependencies. Its current SHA-256 is
`4da290d9baee380b02a5a92bc7811b6574631def9b9acc04af47706028aa1eb6`;
the original commit's manifest is different. The latest local history change to
deployment requirements/workflow is commit
`9b0756f505de81c4ec520f89aa41e0cf96d53683` (20 September 2026), later than the
declared training timestamp. Do not backdate the deployment pin into a full lock.

P README/RUN_GUIDE, Dockerfile and `.github/workflows/ci.yml` prescribe Python
3.11 / python:3.11-slim / Ubuntu app tests, whereas producer metadata declares
Windows Python 3.12.7. These are distinct deployment/test instructions, not a
verified producer environment. The CI workflow installs requirements and tests
the application; it does not publish a producer freeze or checksum-bound reference
pack. O's CI uses Python 3.12 on Ubuntu and executes backend/MySQL/frontend tests;
its `backend/constraints.txt` explicitly says application dependencies, not V17.
O's audit venv has system-site-packages=true; its later observed ML versions remain
candidate audit versions, not producer proof. No interpreter/package-version
command was run in those external environments during this investigation.

File and local Git-history searches found no original scientific dependency lock,
freeze, conda/environment export, notebook or approved reference JSON in the searched
roots. Existing ZIP inspection found duplicated metadata/log/manifests, not missing
runtime evidence. No downloaded CI run logs/artifact containing that evidence was
located. Remote Actions artifacts were not fetched, so absence is limited to the
inspected local material. The only tracked lock in O's matching history search was
frontend/package-lock.json, irrelevant to model production.

Search limits: initial rg hit an inaccessible old pytest-cache directory. A later
os.walk search excluded caches/env/node_modules/secret/runtime directories; it
reported inaccessible O `.phase5-test-temp` and
`.phase9-release/.pytest-phase9-tmp`. Their contents were not claimed inspected.
A filename containing "blocked" produced one spurious lock candidate, a PNG under
O's release screenshots; it is not a dependency lock. No claim that evidence cannot
exist elsewhere or in the producer's original machine/account is made.

### Existing reference candidates (none generated here)

**One original-source demo is recoverable from P `op.txt`, lines 354 onward.** The
log contains all twelve named inputs. Static literal inspection of the frozen
`run_demo_prediction` sample at source line 3564 confirms every displayed field and
value exactly matches that sample. This is an existing hardcoded demo record, not
a real patient case or an output generated by the current callable.

The logged categorical inputs are Disease=`Diabetes Mellitus Type 2`, Symptom
Severity=`Moderate`, Nadi Reading=`Kapha`, Constitution/Prakriti=`Kapha`, Stress
Levels=`Moderate Stress`, Sleep Patterns=`Regular Sleep`, Age Group=`41-60`,
Physical Activity Levels=`Low`. Numeric inputs are BP Systolic=135.0, BP
Diastolic=88.0, Pulse Rate=76.0, Weight (kg)=92.0. Original sample literals provide
the numeric types that the console text alone cannot encode formally.

The four existing printed category values are:

| Target identifier | Value recorded in the original demo log |
| --- | --- |
| Herbal Therapy Strategy | Metabolic Balance Support |
| Lifestyle Recommendations | Active Lifestyle Promotion |
| Therapeutic Yoga Module | Weight Management Yoga |
| Follow-up Recommendation | Follow-up after 15 Days |

These are archived output data, **not clinical advice or newly accepted predictions**.
Source lines 3592/3610/3623/3637 print each returned section's category; the log also
contains reasoning/other enrichment and a manual placeholder, which are excluded
from a four-label fixture. There is no standalone raw_labels/intermediate/index
export in the log. Because the full callable has category defaults, that printed
format alone cannot establish the absence of fallback; the producer must attest
the complete frozen bundle/reference path. Source returns production_bundle at
2827 and the main calls its demo after training/saving, which corroborates the
logged sequence without executing it.

Candidate provenance is stronger than a newly self-generated adapter result:
the demo log is co-committed and co-packaged with the exact frozen artifact/source.
However, no owner approval, complete runtime export, preprocessing intermediate
record or fixture trust attestation was found. The older audit specifically reports
that this demo's Disease spelling is absent from its observed fitted vocabulary;
that is historical candidate evidence, not a new fitted-object inspection here.
Do not silently change it to `Diabetes Mellitus (Type 2)`. Decide whether to approve
it as a frozen unknown-category case or reject it as an accepted positive input
under the future strict policy. That decision remains open.

Other candidates examined:

| Location | Completeness/independence | Disposition |
| --- | --- | --- |
| O `scripts/audit_v17.py`, `tests/real_model/test_v17_parity.py`, `docs/phase5-evidence.md` | Three complete demo-derived input candidates, including Disease substitution and numeric variants; expected enriched dictionaries computed at audit runtime from source AST functions, not a checked-in independent label oracle. Script reports trainingEnvironment=NOT SUPPLIED and referenceApproval=UNAPPROVED CANDIDATES | Historical experiment only; not executed or promoted to approved references; script stdout does not export the expected dictionaries |
| P `tests/test_prediction.py` | Complete 12-field payload and broad result-shape/workflow assertions, no fixed four-label expected mapping | Application test definition, not a persisted producer reference outcome |
| O `tests/backend/test_phase5.py` | Explicitly mocked synthetic workflow outputs | Excluded from real-model parity evidence |
| P training_results, architecture summary, confusion-matrix figures, CatBoost iteration logs | Aggregate outcomes, classes/metrics or candidate training timing, not twelve-input/four-label case pairs | Cannot replace a parity fixture |
| P nested DevOps copy / ZIP | Duplicate original demo/metadata | Corroborating package copy, not additional independent test coverage |

No `ml/reference_cases/authorized-v17.json` or original environment evidence files
proposed in O's phase5 checklist actually exist in the inspected trees/history.
No authoritative reference pack or multiple approved independent cases was found.

### What remains missing and the next approval

1. **Producer identity/runtime attestation:** ask the original producer to confirm
   that the exact committed model/source and log/metadata are from the same export,
   and identify the original unchanged training environment. Co-commit association
   is now recorded; a full environment still is not. Need exact NumPy, pandas, SciPy,
   joblib, XGBoost and transitive versions, Python build/architecture, native-library/
   wheel identities and serializer/protocol information. Original contemporaneous
   freeze/lock/install record is preferred. A freeze collected now is useful only
   if the producer can establish the environment has not changed since production;
   otherwise label it current-state evidence, not original producer versions.
2. **Existing fixture acceptance:** request owner approval of the preserved op.txt
   demo record and its extraction into a four-label reference case, including
   explicit treatment of its unknown-category spelling. No fixture file was created
   or approved by this investigation. Even if accepted, one demo alone does not
   establish broad preprocessing/parity coverage or recover the missing runtime.
3. **If original runtime/reference evidence cannot be recovered:** explicitly approve
   a named experimental runtime/lock and a separately reviewed reference protocol.
   After accepted isolation/deadline/recovery gates, authorize an offline synthetic
   reference run with the unchanged fitted artifact and a reviewed source-equivalent
   raw transform/predict/decode driver, independent of the candidate adapter. Capture
   complete typed inputs, exactly four expected labels, preprocessing intermediates,
   runtime/driver/artifact hashes and approval. Do not retrain, import the training
   module, substitute category values, regenerate the model or use application mocks.

The next approval is **producer/owner confirmation of this committed evidence and
candidate-fixture policy**, plus provision of the original environment export—not
permission to deserialize now. Existing execution-boundary acceptance remains a
separate blocked prerequisite. No version guess, current callable result or archived
CI application pass can clear it. Runtime/fixture blockers are narrowed and more
actionable, not marked passed; V17 is not ready.

Read-only commands included scoped `rg --files`, `rg -n`, Get-Content;
`git --no-optional-locks -C <P/O> log/ls-files/show/rev-parse`; and
`.venv/Scripts/python.exe -B -` snippets using pathlib/hashlib/json/ast/zipfile
and captured Git stdout for comparison. No checkout, fetch, repository write,
ZIP extraction, source/callable import, inference, training or package installation
occurred. Some broad inventories had cache-access/missing-directory errors, noted
above; named evidence reads, bounded ZIP/Git comparisons and JSON/AST checks passed.
Only this readiness report was updated; artifacts/datasets/application/dependencies/
database/ports/Docker/WSL and the existing loading-disabled controls were untouched.

## Current readiness assessment — 14 October 2026 (Asia/Calcutta)

**NOT READY for deserialization or inference.** Artifact identity and declared
contract are freshly verified. Artifact-bound runtime/provenance, an accepted
execution boundary and approved reference parity remain missing. This assessment
authorizes none of those execution steps. Only this existing report was edited;
the original 13 October evidence below remains historical.

Read phase-2a-v17-compatibility-review.md, this report, patient-doctor-access-grants.md,
receptionist-module.md and the current system map before inspection. The local
application now has four roles, read-only patient–doctor grants and receptionist
administration at migration 0006. Those changes settle their own administrative/read
policies; they do not authorize prediction invocation, unreviewed result release,
prescriptions or clinical review writes. No application/auth/port/database change
was made here, and no previous grant/receptionist test was rerun or reclassified
as ML compatibility evidence.

### Fresh identity and runtime evidence

The existing verification-only audit matched the previously recorded hashes on
the actual files. It retains immutable checked bytes; no pickle reader, opcode
interpreter, training import, loader, --load request or inference was invoked.

| File | Bytes | Measured SHA-256 equals recorded approval |
| --- | ---: | --- |
| `ml/artifacts/ayursage_model.pkl` | 13,023,934 | `e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98` |
| `ml/source/AyurSage_Training_v17.py` | 190,567 | `afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3` |

Audit result: CHECKSUMS_VERIFIED_LOADING_DISABLED; loading_enabled/model_loaded/
inference_executed all false. Hash identity proves matching bytes, not trust in
the producer or safety/compatibility of executable serialized objects.

Reused historical metadata and older audit findings rather than rerunning those
experiments. Recorded metadata SHA-256 remains
`17f9cbd1e5f61f38195947ebc2ade6facbd8970278262a8ea4bc29efb8aab239` at the Phase 2A
external metadata path. It declares Python 3.12.7, Windows, sklearn 1.9.0 and XGB;
it lacks a model/source checksum binding and complete dependency versions. These
are historical declarations, **not a verified original training environment**.
Fresh distribution metadata inspection (without importing ML libraries) found:

| Component | Training evidence retained from Phase 2A | Current project environment |
| --- | --- | --- |
| Python/platform | Declared 3.12.7 / Windows; original build/architecture not fully recorded | Root .venv: Python 3.12.7, win32, 64-bit; ml/.venv: Python 3.12.7 |
| scikit-learn | Declared 1.9.0, unbound to this artifact | Not installed |
| NumPy/pandas/SciPy/joblib | Original versions absent | None installed |
| XGBoost | XGB selected/available; original version absent | Not installed |
| CatBoost/SHAP/imbalanced-learn | Historical availability flags without versions | None installed |

ml/.venv has no distributions; both pyvenv.cfg files disable system-site-packages.
Backend requirements remain backend-only. Older observed versions (NumPy 2.4.6,
pandas 3.0.3, SciPy 1.18.0, joblib 1.5.3, XGBoost 3.3.0, sklearn 1.9.0) remain
unapproved candidate observations from the other project, not recovered training
pins. No packages or transitive locks were guessed, installed or changed.

The serving dependency families indicated by source are pandas/NumPy, fitted
sklearn/SciPy objects, joblib serialization and the actual selected estimator's
runtime. XGBoost is required only if an artifact-bound manifest/authorized object
inspection confirms it. Training/plotting/SHAP/SMOTE availability is not a reason
to install those packages for raw inference. Actual pickle class references,
native-library/ABI requirements and serialization protocol remain unverified.

[scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html)
does not support cross-version loading as a compatibility guarantee.
[joblib.load documentation](https://joblib.readthedocs.io/en/stable/generated/joblib.load.html)
states that deserialization can execute Python code.
[XGBoost model-I/O guidance](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)
distinguishes stable model exports from version-sensitive serialized memory
snapshots. These support the trust/runtime gates; their current documentation
versions do not supply pins for this artifact. No export/conversion/re-serialization
of the frozen artifact is proposed or authorized.

### Exact callable and preprocessing contract

Static source/AST inspection, never source execution:

| Position | Required input key | Current structural type |
| ---: | --- | --- |
| 1 | Disease | Nonblank string |
| 2 | Symptom Severity | Nonblank string |
| 3 | Nadi Reading | Nonblank string |
| 4 | Constitution/Prakriti | Nonblank string |
| 5 | Stress Levels | Nonblank string |
| 6 | Sleep Patterns | Nonblank string |
| 7 | Age Group | Nonblank string |
| 8 | Physical Activity Levels | Nonblank string |
| 9 | BP Systolic | Finite number, not bool |
| 10 | BP Diastolic | Finite number, not bool |
| 11 | Pulse Rate | Finite number, not bool |
| 12 | Weight (kg) | Finite number, not bool |

Exact raw target order: **Herbal Therapy Strategy; Lifestyle Recommendations;
Therapeutic Yoga Module; Follow-up Recommendation**. Proposed future raw response
is a mapping with exactly these four keys and their decoded scalar text labels,
not enriched dictionaries. This proposed strict response is not an implemented
callable or an observed artifact result. Doctor Prescription & Care Notes is manual
workflow data, not a fifth model output. Diet/reasoning/confidence are not additional
authorized raw outputs.

The actual frozen source callable is `predict_single(bundle: dict, input_data:
dict) -> dict`, line 2846. Source access pattern:

1. Build a one-row DataFrame in `bundle['input_features']` order, using .get with
   Unknown for missing values and ignoring extra input keys.
2. For `bundle['numeric_cols']`, apply pd.to_numeric(errors='coerce').fillna(0.0).
3. Call fitted `bundle['shared_pre'].transform(X_new)`; do not fit or rebuild it.
4. Select the one global `bundle['best_overall_model']`. For each ordered target,
   call `bundle['models'][target][winner].predict(X_pre)`, flatten and take the
   first result, cast it to int, then decode with
   `bundle['le_output'][target].inverse_transform([index])[0]`.
5. The full source then optionally computes probabilities and returns **five
   top-level entries**: four enriched target dictionaries plus the manual
   PENDING_DOCTOR_REVIEW string. It is not already the strict four-label adapter.

`make_preprocessor` (1351) declares ColumnTransformer: categorical block first,
OneHotEncoder(handle_unknown='ignore', sparse_output=False), then the four numeric
columns as passthrough, remainder='drop'. The fitted category order, transformed
width/dtype and actual feature names must come from the frozen fitted object, not
be reconstructed from declared input names. Training fits shared_pre on X_train
(2093); inference transforms only. Training `normalize_labels` (376, called by
load_and_prepare at 1478) normalizes Stress Levels, Sleep Patterns, Physical
Activity Levels and Symptom Severity; predict_single does not call it. Adding those
normalizations to serving would change the frozen serving semantics and needs an
explicit approved input policy and parity evidence. Structural API validation
does not establish fitted vocabulary or clinical suitability.

Source bundle construction (2699–2737) intends pipeline_version, shared_pre,
le_output, exact input/target/categorical/numeric lists and models[target][winner].
Production model construction can omit a target if its winner is absent; this is
not permission to serve an incomplete bundle. Source expectations, older audit
claims and this checksum do not establish the actual serialized object's graph.

### `v17_callable.py` location and static comparison

**`backend/app/v17_callable.py` is absent in this authorized workspace.** A targeted
read-only search located the named comparator in the older project:
`C:/Users/yvasa/Videos/AYURSAGE/backend/app/v17_callable.py`.
It was inspected without importing, executing, copying or modifying it. Identity:
39,313 bytes, SHA-256
`0da4cf91b6116d96c4725fa7537f0b6d261ca1eb7557ad7575222a0647ab557f`.
Its header's source hash matches the frozen source, and direct AST/literal
comparison establishes the following (header claims alone were not relied on):

| Behavior | Frozen training source | Older external extraction |
| --- | --- | --- |
| predict_single, _patient_seed, _extract_wellness_factors | Source functions | Identical function ASTs, ignoring line locations |
| Feature/target and 12 literal engine/phrase constants | Declared literals | Literal values match; INPUT_FEATURES expression has same categorical-plus-numeric ordering |
| Reasoning RNG | Global random.seed(seed) at 3418 | Invocation-local `random = Random(seed)` at 229; replacing that one AST statement restores exact function AST equality |
| Module initialization | Imports training/plotting/optional packages; warnings/logging/matplotlib mutations | Imports only Random, pandas, NumPy and defines the extracted constants/functions; no training entry point or source module import |
| Raw serving behavior | Numeric defaults, category defaults, optional probability swallowing and enrichment | Retained by the identical predict_single body; not a strict fail-closed raw adapter |

The local RNG change confines reasoning random state in the external source; serial
reasoning parity and concurrency behavior have not been executed or accepted here.
It does not change the statically matched raw-label prediction core. The older
phase5-evidence.md claims bundle inspection/parity in an inherited experimental
runtime; that remains historical, not approval of this workspace or its runtime.
The older extraction may inform a later reviewed adapter, but is not installed,
approved or silently substituted into the current application.

Important source import side effect: lines 163–186 catch missing imblearn and at
170 invoke `subprocess.run([sys.executable, '-m', 'pip', 'install',
'imbalanced-learn', '-q'], ...)`. Avoiding __main__ **does not prevent this import-time
installation attempt**. Other import effects include warnings.filterwarnings at
87, matplotlib backend selection at 90 and logging.basicConfig at 326. The main
entry point (3662–3681) selects a dataset/fallback, trains and runs a demo. None was
executed. The proposed boundary prohibits whole-module import and auto-installation.

### Parity risks and required reference evidence

The strict future adapter must reject missing/extra/null/bool/nonfinite/bad-type
inputs and legacy null stored assessments before transform; preserve explicit zero
and supplied values; validate exact bundle lists, fitted state and four classifiers;
and reject malformed prediction shape or class indices before decoding. The source
currently flattens/takes the first result and casts to int, which is weaker than
validating one scalar class per one-row input. No fallback classifier is permitted.

Unknown categories become ignored/all-zero one-hot blocks in source. Whether the
service rejects them or permits that frozen behavior is an unresolved collection/
serving policy, not an invitation to invent aliases. Inference vocabulary must be
bound to the actual fitted categories. Input spelling, case/whitespace, DataFrame
column order, numeric conversion, transformed dtype/width/order, winner selection
and label encoder classes are all parity checkpoints.

Missing raw categories after an incomplete target list receive source defaults
at 2916–2919. A missing classifier access itself raises an error; it is not a
fallback estimator selection. Probability exceptions at 2899–2912 become None;
lifestyle/yoga details have fallback mappings; wellness factors default numeric
values at 3064–3071. Reasoning and dietary/yoga enrichment are outside the approved
four-label contract. None may manufacture success in a future inference API.

Obtain a producer/owner-approved **synthetic reference pack** from an existing,
trusted compatible serving environment using the unchanged fitted artifact—no
retraining. Pack must bind model/source/runtime/reference-driver hashes and contain
exact ordered inputs, approved categorical vocabulary, numeric representations,
transformer output feature order/shape/dtype and reference transformed values or
digests, encoder class/index mappings, and exactly four decoded expected labels.
Expected labels must be independent of the candidate adapter, not copied from its
own output or invented from source bucket rules/demo prose. Use a reviewed pure
transform/predict/decode reference driver without importing the training module.

After separate authorization, compare preprocessing intermediates first, then each
classifier's scalar index and decoded label. Require exact four-label equality;
any numeric comparison tolerance must be approved in advance rather than selected
after seeing discrepancies. Cover approved categorical classes/combinations,
numeric zero/precision fixtures, repeated and concurrent calls, invalid/extra/missing
inputs and the approved unknown-category policy. Test failures must remain failures,
not fallback labels. Successful parity would establish reproduction for those
fixtures/runtime, not clinical efficacy or patient-release approval.

### Safe execution boundary proposal (no boundary launched)

Retain the single Flask architecture and existing ml/inference boundary; first
tests are offline synthetic audits, not new clinical endpoints or a second API.
Use a separately approved disposable, network-denied isolated guest/worker with
non-admin identity, minimal read-only model plus reviewed code/runtime/reference
inputs, no training/dataset execution, no host workspace/root venv, patient database,
JWT/cloud/email credentials, Docker socket or inherited secrets, and bounded scratch
only. Match the producer's verified OS/build/architecture; if Windows evidence is
confirmed, an isolated Windows guest is a candidate, not an assumed Linux port.
No VM/container/service or Docker/WSL change is made or authorized by this report.

Approve numeric CPU/memory/PID/output/scratch/time limits and the image/runtime/code
identities before execution. Existing harmless-probe 256 MiB and watchdog timing
numbers are not a measured ML budget. A supervisor outside the execution boundary
must cover startup, loading, validation, prediction and teardown with a hard wall
deadline; survive worker/coordinator failure; kill the full execution scope; and
record exact identities/exits independently. Verify network/read/write/resource
restrictions and fault recovery with harmless fixtures first. No automatic retries,
model substitutions, runtime repair, package installation or limit expansion.

Existing Step 1.3 remains NOT ACCEPTED. Reused the current report's evidence and
statically checked the relevant control/watchdog functions: observer reports
container-level exit only, parent/child acceptance false; independent coordinator/
daemon-failure recovery and unconditional deadline enforcement remain unvalidated.
`reports/step-1-3-5-beeaf978742c/verification-results.json` still records live worker
tests skipped, step_1_3_accepted false and model_loaded false. A venv, container
stopped-state or late-result rejection alone does not clear this gate. This proposal
does not replace or bypass those requirements; they must be demonstrated for the
specifically approved boundary before pickle execution.

Read and hash staged artifact bytes inside the approved boundary and pass the same
retained VerifiedArtifact.buffer to the reviewed deserializer (no path reopen or
memory-mapped alternative). Treat compatibility warnings as a rejected attempt;
record bounded, secret-free structural diagnostics. Whole-source import, training,
refitting, artifact writes and persistence conversion are excluded. Do not inspect
live object contents merely because a hash matched; trust/runtime/boundary approval
must already exist.

### Ordered plan and approval gates for the first inference test

| Order | Evidence/action | Exit criterion / explicit approval |
| ---: | --- | --- |
| 1 | Producer attestation tying both verified hashes to metadata, origin/export chain and intended production bundle; request trusted object/vocabulary/class manifest | Artifact trust/provenance accepted; identity alone is insufficient |
| 2 | Recover original complete package/native/build evidence and transitive lock, including XGBoost if applicable; otherwise document an explicitly named experimental runtime | Runtime and exact lock/wheel identities approved; environment preparation separately authorized; no guessed original pins |
| 3 | Resolve strict vocabulary/normalization policy and obtain independently approved synthetic reference pack with raw labels/intermediates | Raw four-label contract and reference pack approved; no clinical enrichment or fabricated defaults |
| 4 | Review bounded worker/supervisor protocol and limits; separately authorize preparation and harmless boundary/failure tests | Actual restriction, deadline, observer and independent recovery evidence passes; existing failed watchdog criteria are not bypassed |
| 5 | Review source-equivalent transform/predict/decode adapter and same-buffer loader code/identities as a separate implementation slice | No source import/auto-install; exact schemas and fail-closed warnings/outputs; loading remains disabled by default |
| 6 | Explicitly authorize ONE bounded load/structure-only attempt against these exact hashes/runtime/boundary | Verify actual serialization, pipeline_version, exact ordered lists, fitted transformer/vocabulary/classes, winner and four required classifiers; stop on any warning/mismatch/timeout; no predictions in this stage |
| 7 | After structural acceptance, explicitly authorize bounded synthetic inference/reference parity | One approved one-row transform, exactly four selected predict/decode calls, exact labels and intermediate comparisons; repeated/concurrent and failure checks within approved budget |
| 8 | Record artifact/source/runtime/adapter/fixture hashes, identities, limits, warnings, timing, exit/cleanup and parity outcome | Accept only actual complete evidence; no endpoint/UI/clinical-release/prescription activation |

The minimum gates **before deserialization** are trusted artifact provenance,
approved compatible or explicitly experimental runtime, accepted bounded execution
and recovery evidence, reviewed loader/structure protocol and explicit load
authorization. Reference/input policy is additionally required before the first
inference/parity stage. The whole ordered inference plan remains blocked until
these gates are met; this assessment is not that approval.

### Blockers and what clears them

| Blocker | Current status | Required evidence |
| --- | --- | --- |
| Artifact identity | PASS for the two recorded byte identities | Recheck same buffers inside any later approved worker; no identity mismatch currently |
| Artifact/runtime provenance | OPEN | Producer-signed/attested model+source+metadata binding and export/environment record |
| Full compatible runtime | OPEN; ML packages absent, original transitive pins absent | Original environment/lock/native build evidence, or explicit experimental lock approval with clear limitations |
| Fitted object graph/vocabulary | OPEN; source declarations only | Artifact-bound manifest first; confirm actual fitted state/classes in authorized structure-only load |
| Accepted execution boundary | BLOCKED; Step 1.3 not accepted | Approved boundary plus actual surviving observer, hard deadline and independent-failure recovery evidence |
| Current serving callable | ABSENT; older external extraction is not current code | Review/approve a minimal raw adapter in this workspace after prerequisite gates; do not import/copy the older enriched callable silently |
| Input policy and independent parity references | OPEN | Approved fitted vocabulary/unknown-value/normalization policy and independent synthetic reference pack |
| Clinical service/release/review integration | OUT OF SCOPE / not authorized | Separate invocation/result-visibility and provenance/idempotency policy; existing read grants do not authorize predictions or release |

Dataset provenance remains unresolved as recorded in Phase 2A; obtain producer
lineage if claiming training reproducibility/clinical suitability. This assessment
neither selects/rebuilds a dataset nor makes that claim. No retraining is needed or
authorized to perform later parity on the frozen fitted artifact.

### Commands and actual verification limits

Executed from the workspace root:

```powershell
ml/.venv/Scripts/python.exe -B -m ml.inference.audit
.venv/Scripts/python.exe -B -c "import sys,platform,importlib.metadata as m,json; names=['numpy','pandas','scipy','scikit-learn','joblib','xgboost','catboost','shap','imbalanced-learn']; installed={d.metadata['Name'].lower():d.version for d in m.distributions()}; print(json.dumps({'python':sys.version.split()[0],'platform':sys.platform,'architecture':platform.architecture()[0],'packages':{n:installed.get(n,'NOT INSTALLED') for n in names}},indent=2))"
ml/.venv/Scripts/python.exe -B -c "import sys,importlib.metadata as m,json; print(json.dumps({'python':sys.version.split()[0],'distributions':[(d.metadata['Name'],d.version) for d in m.distributions()]}))"
```

Each command individually succeeded, exit 0; audit flags all false. Read-only
Get-Content/rg inspected source, controls and reports. Pure AST/literal comparison
commands using `.venv/Scripts/python.exe -B -` succeeded, exit 0: exact source/API
ordered literals match; frontend contains all twelve input names; external
predict_single/helpers and all literal constants match as described; only the
reasoning seed statement differs. No candidate callable or ML package was imported.
Initial combined inspection returned exit 1 for absent current v17_callable and
an older project's inaccessible pytest-cache directory; direct named-file reads
and AST comparison resolved the comparator location without altering that project.
A guessed tests/ml/test_checksums.py path was absent; actual test module is
test_loading_scaffold.py. No tests were executed from either path.

No regression/ML/worker/Docker audit was rerun: this is a documentation-only static
assessment plus requested checksum/environment evidence, not compatibility tests.
No loading, predictions, probability calls, source execution, dependency installs,
database connections/migrations, process restarts, port changes or clinical
operations occurred. No runtime/parity or V17-integration completion claim is made.

## Original preparation decision — 13 October 2026

13 October 2026, Asia/Calcutta. **NOT READY for deserialization or a prediction
service.** This milestone specifies the missing evidence and acceptance gates;
it does not authorize installation, loading, worker execution or endpoint work.
Phase 2A remains the detailed evidence record. Only this report is added.

## 1. Facts versus assumptions

- Phase 2A verified the approved model (13,023,934 bytes, SHA-256
  `e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98`) and source
  (190,567 bytes, SHA-256
  `afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3`). The
  preservation inventory in this preparation also matches those bytes.
- `ml/inference/checksums.py`: `read_verified_file`, `VerifiedArtifact` and
  `verify_workspace_buffers` retain immutable, checksum-verified bytes. A future
  loader must consume that buffer without reopening its path. Identity is not
  evidence of compatibility or safety of executable pickle contents.
- `ml/inference/audit.py`: `run_audit` has no deserializer; loading requests raise
  `LoadingDisabled`. No loading request or --load invocation was made here.
- Source `train_ayursage`, bundle construction at lines 2699-2737, writes with
  `joblib.dump(production_bundle, ...)`. It intends a dictionary with shared_pre,
  le_output, ordered feature/target lists and models[target][winner]. This supports
  a **joblib/pickle-based bundle expectation**, not a verified internal format.
  Actual compression/protocol, class references, fitted state and winner remain
  uninspected. A .pkl suffix alone establishes none of them. No opcode parsing or
  deserialization was performed; existing evidence does not settle these details.

## 2. Runtime evidence and concrete unresolved actions

The Phase 2A JSON evidence is
`C:/Users/yvasa/Downloads/AYUR_mega/AYUR_mega/results/metadata.json`
(SHA-256 `17f9cbd1e5f61f38195947ebc2ade6facbd8970278262a8ea4bc29efb8aab239`).
It declares AyurSage_v17, XGB, Windows, Python 3.12.7 and sklearn 1.9.0, but lacks
a model checksum binding. Source metadata writer at lines 2786-2807 records only
Python/sklearn versions and availability flags, not a complete runtime lock.

| Component | Historical training metadata declaration | Older observed audit runtime |
| --- | --- | --- |
| Python / OS | 3.12.7 / Windows | Python 3.12.7 |
| scikit-learn | 1.9.0 | 1.9.0 |
| NumPy | Version absent | 2.4.6 |
| pandas | Version absent | 3.0.3 |
| SciPy | Version absent | 1.18.0 |
| joblib | Version absent | 1.5.3 |
| XGBoost | Available, XGB selected; version absent | 3.3.0 |

Observed versions come from the older `Videos/AYURSAGE/docs/phase5-evidence.md`,
whose environment inherited packages. They are **not original pins, an approved
lock or compatibility proof**. Phase 2A observed project Python 3.12.7/Windows;
root .venv lacks the listed ML packages and ml/.venv has no distributions. Both
pyvenv.cfg files disable system-site-packages. Backend requirements contain no ML
dependencies. These unchanged observations were not redundantly remeasured here.
The serving core needs pandas/NumPy, joblib and fitted sklearn dependencies;
XGBoost is expected only if the actual bundle confirms XGB. Optional CatBoost,
SHAP, imbalanced-learn and plotting imports are not automatically serving needs.

| Unresolved item | Concrete next action or explicit deferral |
| --- | --- |
| Metadata-to-model provenance | Obtain producer attestation/export binding model/source hashes to the training metadata; until then treat declarations as historical, not verified original runtime |
| Missing original NumPy/pandas/SciPy/joblib/XGBoost and transitive versions | Request the producer's environment export/lock, Python build/architecture, OS, native library and wheel/build evidence; no installation from guesses |
| Original environment unrecoverable | Obtain explicit approval for a named experimental candidate runtime, resolved transitive lock/wheel hashes and limitations; test it as an experiment, never label it original reproduction |
| Actual serialization and object graph | Seek a trusted artifact-bound manifest first; validate format/classes/schema during the first authorized isolated load. Deferred because inspection of live objects requires deserialization |
| Windows versus Linux/native ABI compatibility | Match documented Windows/Python context first if reproducing it; treat Linux as a separate portability experiment. Image existence/digest/runtime must be inspected under later authorization |
| Vocabulary, label classes and normalization | Obtain artifact-bound category/class exports and approved input policy; confirm against fitted components after safe loading. Do not infer aliases from the demo |
| Approved reference predictions absent | Obtain synthetic inputs and exact four decoded labels, independently approved and bound to artifact/source/runtime. Older demo variants/parity claims are not acceptance fixtures |
| Dataset provenance unresolved | Defer to a separate provenance review; no dataset is selected, changed or retrained here. It limits training-reproduction claims, not a reason to fabricate runtime evidence |

## 3. Execution boundary: inspected controls and blockers

Static inspection, **not live verification**:

- `infra/docker/worker_control_audit.py::create_worker` accepts only fixed harmless
  probes. It specifies pinned image identity, pull=never, network=none, read-only
  root/two mounts, user 1000:1000, dropped capabilities, no-new-privileges, PID/
  CPU/memory caps, no restart, bounded logs and writable scratch. It does not
  mount or load a model. Its 256 MiB probe memory cap is not proven suitable for ML.
- `worker_control_probe.py::controls` checks read-only writes, isolated networking,
  environment allowlisting and absence of the Docker socket. Definitions and
  earlier harmless evidence do not prove a current ML worker is configured safely.
- `worker_watchdog.py::monitor`, `DockerWorker.command`, `verify_descendants`,
  `recover`, `completion`, `audit`: harmless audit uses start+35 s budget and
  start+25 s termination threshold. Docker/WSL commands have individual timeouts;
  recovery loops, sequential calls, scheduling, filesystem operations and final
  process waits can overrun. Result rejection after a late return is not guaranteed
  termination at the deadline. These numbers are not an authorized model budget.
- `worker_diagnostic_audit.py::observe_container_exit` explicitly reports only
  container exit, parent/child verification=false, accepted=false and
  recovery_required=true. `worker_diagnostics.py::classify_tracked_termination`
  validates supplied records; it does not implement a surviving observer.
- The latest Step 1.3.5/1.3.1 report in `v17-loading-audit.md` retains **NOT ACCEPTED**:
  no validated external observer survives teardown; Docker-to-WSL PID identity was
  unproven; disappearance checks were inconclusive. Independent recovery for
  coordinator/daemon failure and an unconditional hard deadline are unverified.
  Heartbeat replacement retries do not bound stuck filesystem calls.

Before loading, require a separately reviewed and evidenced boundary with:
trusted same-buffer inputs; non-admin execution; only read-only artifacts and
reviewed serving/audit code; no source import, patient data, credentials, host
workspace/root venv, cloud identity or Docker socket; enforced network denial;
approved CPU/memory/PID/scratch/log bounds; an external deadline covering startup,
load, validation and completion; surviving exact process identity/exit evidence;
failure recovery independent of the monitored worker; safe cleanup and diagnostics.
Compatibility warnings, timeout or incomplete evidence must reject the attempt.

**Next action:** submit a bounded execution proposal and validate it with harmless
fixtures under separate authorization. Establish the actual parent/child mapping
and observer survival, failure recovery and timing evidence before allowing pickle
execution. Step 1.3 stays deferred; this report neither fixes nor bypasses it.
If that prerequisite remains deferred, model loading is also deferred. No Docker
command, worker launch or acceptance audit was run in this milestone.

## 4. Exact contract and proposed correction scope

All source references below are to `ml/source/AyurSage_Training_v17.py`.
Declarations at lines 200-231 define, in order:

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

The first eight are categorical; the last four numeric. Raw outputs, in order:
Herbal Therapy Strategy; Lifestyle Recommendations; Therapeutic Yoga Module;
Follow-up Recommendation. No prescription, diet, reasoning or confidence field
is a fifth raw ML output.

| Location | Finding | Minimal proposed correction in a separate future adapter |
| --- | --- | --- |
| predict_single, 2868-2872 | Missing fields become Unknown; numeric coercion failures become 0.0; extra keys ignored | Require exact complete typed input before any transform; revalidate stored inputs; preserve explicit values; no defaults |
| make_preprocessor, 1351; normalize_labels, 376 | OHE ignores unknown categories; training normalization is not called in predict_single | Validate fitted vocabulary under an approved policy; preserve feature/order/transformer; do not add normalization/aliases silently |
| predict_single, 2889-2894 | Four separate classifier predictions and encoder decoding form the raw-label core | Reuse frozen fitted components; validate prediction shape/class index and exact complete target set; no fitting or new estimator |
| predict_single, 2899-2912 | Probability failures are swallowed as confidence=None | Keep confidence outside the minimal four-label contract; if later approved, specify failure semantics and test it |
| predict_single, 2916-2929 | Missing labels receive Preventive Wellness Lifestyle / Stress Reduction Yoga / Metabolic Balance Support / Regular Wellness Follow-up; engine details have fallbacks | Reject incomplete outputs/bundles; return decoded labels only, not manufactured success |
| predict_single, 2935-2977 | Adds reasoning, lifestyle/diet/yoga guidance and manual PENDING_DOCTOR_REVIEW slot | Exclude enrichment and placeholder from raw-label serving; treat any review status separately as authorization/persistence policy |
| _extract_wellness_factors, 3036, 3064-3071; generate_clinical_reasoning, 3390, 3418 | Numeric fallbacks 120/80/70/75 and global random.seed; further default labels | Do not call these functions in the minimal adapter; enrichment/concurrency changes require separate scope |

No correction was implemented. Preserve the model, source, feature names/order,
fitted preprocessing, classifiers and label decoders. Compare valid-input raw
labels against approved references before accepting an adapter; rejection of
invalid inputs must be explicit, not a silent change to medical behavior.
Current `assessment_payload` already validates completeness/types but not fitted
categories; legacy SQL NULL and direct ORM writes still need inference validation.

## 5. First authorized load/parity checklist and service exit criteria

1. Resolve artifact-bound evidence, approved runtime/lock and synthetic reference
   labels; approve resource/deadline and categorical policy. No guessed pins.
2. Separately authorize environment preparation and prove the required boundary
   with harmless fixtures. If deadline/observer/recovery evidence fails, stop.
3. Review a loader consuming VerifiedArtifact.buffer and a raw-label adapter;
   preserve loading-disabled defaults. Never import/execute the training module.
4. Separately authorize one bounded **load/structure-only** attempt. Confirm actual
   runtime, serialization, exact lists, fitted state, encoder classes, selected
   algorithm and one expected classifier per target. Reject warnings/mismatch;
   do not repair, refit, swap models or increase limits automatically.
5. After structural acceptance, authorize bounded fixture parity: exact four labels,
   repeatability/concurrency, invalid/missing/unknown inputs, decode failures,
   timeout and no fallback/enrichment. Record artifact/source/runtime/fixture hashes.
6. Only then design prediction service authorization and assessment-linked result
   provenance/status/idempotency. Doctor/admin access remains denied without grants;
   owner identity alone must not bypass unapproved-result release policy.

Proceed to service implementation only when **all** loading/structure/parity and
boundary gates have actual passing evidence; the runtime lock and raw contract are
approved; failure and persistence semantics are agreed; and result visibility/
doctor-review policy is explicit. Existing assessments lack prediction version,
run status and output storage: next action is a reviewed additive persistence/API
design, not repurposing notes or inputs. API tests must cover JWT/role/cross-patient
denials before inference, generic failures/no sensitive logs, rollback, correct
actor/input/provenance linkage and retries. Service implementation and real DB/
deployment acceptance remain separate milestones; no readiness gate is marked passed.

## 6. Focused safe checks and preservation

Purpose: validate only the existing same-buffer/rejected-byte prerequisites and
exact source/API naming used by this proposal. Did not repeat Phase 2A's 77-test
suite, pip check, route listing, environment inventory or full checksum audit;
their recent results are historical evidence, not new executions here.

Exact test commands from the workspace root:

```powershell
ml/.venv/Scripts/python.exe -B -c "import unittest; suite=unittest.defaultTestLoader.discover('tests/ml'); names={'test_replaced_path_cannot_change_retained_verified_buffer','test_unverified_bytes_cannot_construct_verified_object'}; tests=[test for group in suite for case in group for test in case if test._testMethodName in names]; result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests)); raise SystemExit(not result.wasSuccessful())"
.venv/Scripts/python.exe -B -c "import unittest; suite=unittest.defaultTestLoader.discover('tests/backend'); tests=[test for group in suite for case in group for test in case if test._testMethodName=='test_feature_and_output_names_match_frozen_source_without_importing_it']; result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests)); raise SystemExit(not result.wasSuccessful())"
```

Results: **2 opaque-byte tests, 0.023 s, OK, exit 0** (approved temporary-fixture
access); **1 contract-name test, 0.280 s, OK, exit 0** (isolated SQLite setup,
source parsed as AST, never executed). No loading branches or --load calls.
Read-only inspection used Get-Content/Select-Object and rg for the listed files.
An rg search using `infra/docker/*.py` failed with Windows error 123; corrected
directory/glob search below exited 0 and located the actual observer function:

```powershell
rg -n 'def observe_container_exit|observe_container_exit|def classify_tracked_termination|def publish|def audit|start\+35|start\+25|def recover' infra/docker -g '*.py'
```

Before/after preservation inventory uses:

```powershell
.venv/Scripts/python.exe -B -c "import hashlib,json,pathlib; roots=['backend','tests','docs','ml','infra','frontend']; paths=[p for root in roots for p in pathlib.Path(root).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','.venv','__pycache__','.npm-cache'))]+[pathlib.Path(x) for x in ['README.md','.env.example','.gitignore']]; print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))"
```

Both inventory commands exited 0. Comparison: **all 55 existing inventoried files
unchanged; no removals; only docs/setup/phase-2b-readiness.md added**. This includes
the model/source/dataset, loading controls, worker/watchdog code, prior reports,
application, dependencies and workflows within the inventoried roots. No Git
repository exists, so no Git diff/commit is claimed. Excludes caches,
bytecode and environments. No installation, pickle/opcode execution, training,
worker launch, watchdog tests, Docker operations, endpoint/frontend changes,
live MySQL, production migrations or deployment were performed. Stop here.
