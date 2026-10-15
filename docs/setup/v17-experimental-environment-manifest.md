# Frozen AYUR-SAGE V17: Route B experimental environment manifest

Draft for approval, 14 October 2026 (Asia/Calcutta). **PLAN ONLY; NOT RESOLVED,
NOT INSTALLED, NOT COMPATIBILITY VERIFIED, NOT REPRODUCIBLE.** Route B proposes a
new experimental runtime; it does not recover the original producer environment.
Approval of this document alone does not authorize any execution.

## Location and scope

This is the single environment manifest in `docs/setup`, beside
[Phase 2B readiness](phase-2b-readiness.md),
[Phase 2A review](phase-2a-v17-compatibility-review.md) and the
[loading audit](v17-loading-audit.md). Those reports remain the evidence and gate
records; they are not replaced or copied into new reports. Inspection found no
existing experimental manifest at this path. The
[metadata network design](../../tools/v17_metadata_audit/NETWORK_DESIGN.md) governs
the proposed transport, not an approved environment or working resolver.

At initial drafting only this document was created. The later authorized static
provider milestone edits the existing audit code/tests and network design only,
plus this manifest's status/identities. Application architecture,
backend manifests, environments, frozen model/source and datasets stay unchanged.
No environment directory is created. A future disposable environment must have a
new, owner-approved path, disabled system-site-packages, and no inherited packages;
do not repurpose root `.venv`, `ml/.venv` or the older inherited audit environment.

## Evidence ledger and terminology

**Observed** means a local file declares a version or an older report records it;
it does not mean the package was inspected or executed now. **Proposed** means an
exact candidate for future review. **Verified compatibility** requires independent
target metadata/tag evidence and later authorized native/model checks; none is
established here. Historical test claims are not new verification.

| ID | Inspected evidence | What it establishes / limit |
| --- | --- | --- |
| E1 | `C:/Users/yvasa/Downloads/AYUR_mega/AYUR_mega/results/metadata.json` | Declares Python 3.12.7, Windows, sklearn 1.9.0, selected XGB; optional availability flags without versions. No full runtime, architecture/build or artifact-hash field. Read as text only |
| E2 | `C:/Users/yvasa/Videos/AYURSAGE/docs/phase5-evidence.md`, Runtime and parity scope | Records six scientific-package versions in an inherited experimental environment. Not a producer lock, approved parity or current compatibility |
| E3 | `tools/v17_metadata_audit/proposed.py`, `CANDIDATES`, `TARGET`, `CLIENT`, parsing/transport/audit routines | Eleven fixed candidates and target markers; restricted synthetic checker, no HTTP adapter or version selection |
| E4 | `tools/v17_metadata_audit/test_proposed.py`, `valid()` and test definitions | Synthetic requirements and placeholder filenames only; tests say proposed/unexecuted. Does not establish real dependency edges or wheel availability |
| E5 | `tools/v17_metadata_audit/NETWORK_DESIGN.md` | Proposed request limits, sidecar provenance rules and incomplete grammar/tag/evidence producer |
| E6 | `.venv/pyvenv.cfg`, `ml/.venv/pyvenv.cfg`, Phase 2B readiness | Configurations declare Python 3.12.7, no system packages; ML venv created without pip. Prior readiness records root runtime as win32/64-bit and absent ML distributions; not rerun |
| E7 | `.venv/Lib/site-packages/pip-24.2.dist-info/METADATA` and `pip/_vendor/vendor.txt` | Local metadata declares pip 24.2 (Requires-Python >=3.8), resolvelib 1.0.1 and packaging 24.1. No pip/import/version command run |
| E8 | Frozen `ml/source/AyurSage_Training_v17.py`, static text; Phase 2A/2B/loading reports | Intended serialization/preprocessing contract and outstanding loading gates, not current fitted-object inspection |

Phase 2B records strengthened co-commit/co-package association of E1 with the
unchanged artifact/source, but not a complete producer-runtime attestation. The
older Phase 2A wording about unbound metadata must be read with that later update.
Producer deployment ranges, later sklearn pin and Python 3.11/Linux CI instructions
are not a Python 3.12.7/Windows training lock.

Read-only PowerShell file inspection and SHA-256 hashing recorded these **previous
0.1.0 review identities**, now superseded by the static provider milestone below;
no file was imported or tested:

| Audit file | Bytes | SHA-256 |
| --- | ---: | --- |
| `proposed.py` | 21,093 | `ee58b405be05e802042ca7b0137fb77c1c2a8b06a5ef6bed4b206c2f192591f1` |
| `test_proposed.py` | 25,071 | `100076305861b91880e27ab22b9523acbf2544ca108284a52837eaf84264e104` |
| `NETWORK_DESIGN.md` | 5,759 | `0915df1030028d4eaa0192450d361daa6b94b3f3465cbef2bcf2f643b3c13ceb` |

## Proposed target and exact candidates

Target: **CPython 3.12.7 / Windows AMD64**, 64-bit standard CPython. Marker values:
implementation_name=cpython, implementation_version=3.12.7,
python_version=3.12, python_full_version=3.12.7,
platform_python_implementation=CPython, os_name=nt, sys_platform=win32,
platform_system=Windows, platform_machine=AMD64, extra="". Windows release/build,
interpreter build/installer identity and actual complete supported tag set remain
unresolved. E6 is supporting configuration evidence, not proof of this new target.

Every version below is a **proposed experimental candidate**, not an approved pin.
Public existence, Requires-Python, wheel availability, dependency consistency,
native ABI compatibility and V17 compatibility are **UNVERIFIED for every row**.

| Distribution | Proposed version | Observed/declaration evidence |
| --- | --- | --- |
| scikit-learn | 1.9.0 | E1 declaration; E2 historical observation; E3 candidate |
| numpy | 2.4.6 | E2 historical observation; E3 candidate; producer version absent |
| pandas | 3.0.3 | E2 historical observation; E3 candidate; producer version absent |
| scipy | 1.18.0 | E2 historical observation; E3 candidate; producer version absent |
| joblib | 1.5.3 | E2 historical observation; E3 candidate; producer version absent |
| xgboost | 3.3.0 | E2 historical observation; E3 candidate; E1 selects XGB without version |
| threadpoolctl | 3.6.0 | E3 proposal only; no inspected installed/producer version evidence |
| narwhals | 2.24.0 | E3 proposal only; no inspected installed/producer version evidence |
| python-dateutil | 2.9.0.post0 | E3 proposal only; no inspected installed/producer version evidence |
| six | 1.17.0 | E3 proposal only; no inspected installed/producer version evidence |
| tzdata | 2026.3 | E3 proposal only; no inspected installed/producer version evidence |

Serving families indicated by E8 are pandas/NumPy, fitted sklearn/SciPy objects,
joblib serialization and the actual estimator runtime. XGBoost is provisionally
included because E1 selects XGB and E2 reports XGBClassifier; actual artifact
references still require separately authorized inspection. CatBoost, SHAP,
imbalanced-learn, plotting/training packages and application dependencies are
excluded pending artifact-bound justification; no missing versions are invented.

## Transitive dependency status

Known **synthetic** edges in E4 (not authenticated package metadata):

| Synthetic parent | Dependencies represented by test fixtures |
| --- | --- |
| scikit-learn | numpy, scipy, joblib, narwhals, threadpoolctl |
| pandas | numpy with a Python marker, python-dateutil, tzdata with a Windows marker |
| scipy | numpy |
| python-dateutil | six |
| xgboost | numpy, scipy; nvidia-nccl-cu12 behind platform_system == Linux |

The fixture's Linux-only NCCL edge evaluates inactive for the proposed target;
this is not evidence that real XGBoost metadata has that exact condition. No NCCL
version is proposed. Empty requirements for other synthetic fixtures do not prove
those real distributions are dependency-free. Actual Requires-Dist, bounds,
markers, extras, all recursive edges and native DLL requirements are unresolved.
An unknown applicable dependency or version conflict must stop review, with the
parent/requirement recorded; never expand the eleven-project map automatically.

## Exact tooling requirement before metadata resolution

Recorded local tooling: **pip 24.2; vendored resolvelib 1.0.1; packaging 24.1**,
from E7. The initial draft proposed these as new requirements; the authorized
synthetic provider milestone supersedes that choice with the standard library
only. Standalone installations are neither assumed nor required. There is no
demonstrated functional need for pip or alternative-version search in fixed-map
closure checking. Pip remains evidence only: **do not invoke pip for this metadata phase**,
including install, download, index, check or dry-run. Its vendored resolver is not
an approved sidecar-only provider and must not be used via pip's acquisition path.

The synthetic fixed-candidate provider now exists in the existing `proposed.py`,
client **ayursage-metadata-audit 0.2.0-proposed**, with definitions in the existing
`test_proposed.py` and contract in `NETWORK_DESIGN.md`. It accepts bounded in-memory
JSON index/sidecar fixtures only, verifies advertisement binding and an explicit
target tag policy, and reuses the restricted parsers for fixed dependency closure.
No general resolver or HTTP provider is implemented. Whether a future complete
parser/tag implementation uses packaging 24.1 or another reviewed implementation
remains a separate decision; vendoring evidence does not establish suitability.
Any real-metadata provider needs exact reviewed identity and independently reviewed
transport before authorization. Tool acquisition needs separate approval.

The legacy `audit(WheelFixture)` entry point remains a restricted fixed-map
synthetic checker; the new `audit_index` is also **synthetic-only**. Neither can
select alternatives or emit independently verified real-resolution status. Its
ASCII/header-only metadata subset rejects descriptions, folded/Dynamic headers,
extras and many legal PEP 440/508 forms. Real metadata may therefore reject even
when valid. Do not strip headers/bodies or approximate unsupported expressions to
force acceptance. This milestone changes code/test definitions under explicit
static-implementation authorization; execution is still separately prohibited.

## Static provider milestone review identities

Updated 14 October 2026. Current byte sizes and SHA-256 values are recorded below
after static edits. These replace the previous audit identities; no test pass,
real resolution or compatibility follows from these hashes.

| Audit file | Bytes | SHA-256 |
| --- | ---: | --- |
| `proposed.py` | 34,504 | `0c3add1341942b2e7cea1d04b21291fa9e5134a999145b16a907dcf709837a12` |
| `test_proposed.py` | 45,152 | `af6133491889f8ec2a38f4385f903c5d33e236bfce31d2c246e3b4f764a74586` |
| `NETWORK_DESIGN.md` | 12,463 | `80ee15f8b27d5ab166e6843b7a585ae83d271fdbe4caf58dc726df90eab58e1a` |

The contract and acceptance definitions cover synthetic advertisement binding,
request/archive denial, explicit target tags, Requires-Python, yanked/duplicate
and variant policies, recursive fixed closure, markers/conflicts, deterministic
output and bounded malformed-input rejection. Nothing is empirically proven by
the newly written fixtures until separately authorized execution. Real index
responses, complete parser/tag coverage, transport enforcement, native/model
behavior and durable authenticated evidence remain unverified. All later steps
below remain future work; none is authorized by static implementation.

## Future metadata-only procedure (requires approval; not executed)

1. Approve candidates, target markers, exact tooling/provider identity and the
   metadata transport/evidence policy. Independently review archive denial and
   validate controls using harmless fixtures under separate execution approval.
   Use no model, dataset, patient data, secrets or application environment.
2. Use only canonical `https://pypi.org/simple/<normalized-project>/` index pages
   for the eleven approved names. No extra index, mirror, direct/VCS requirement,
   credentials, redirect, retry, cache reuse or automatic candidate expansion.
   Reject non-200 responses or a changed final URL. No network is authorized now.
3. From authenticated index responses, enumerate exact-version wheel filenames;
   parse/verify project and version, yanked status, Requires-Python and complete
   CPython 3.12.7 Windows AMD64 supported-tag intersection. Include applicable
   pure-Python/abi3 tags, not just a guessed cp312 filename. Reject absent compatible
   wheels, ambiguous/conflicting variants or source-only candidates; no sdist,
   wheel archive, range request, archive HEAD/probe, build or fallback retrieval.
4. Retrieve only separately advertised PEP 658/714 `.whl.metadata` sidecars with
   advertised SHA-256. `https://files.pythonhosted.org:443` requires explicit,
   separate host approval under E5; index approval alone does not grant it. Bind
   each exact sidecar URL/hash to its originating approved page, verify returned
   bytes, and reject missing/unsupported advertisements or hash mismatches. A
   supplied fixture hash alone is not advertisement provenance.
5. With the reviewed metadata-only provider, validate Name/Version/Requires-Python,
   parse every Requires-Dist and evaluate markers against this target with no
   extras. Check all eleven candidates as roots and every applicable recursive
   requirement against their fixed versions. Never auto-select a replacement.
   Reject unknown Windows release/build markers, unsupported syntax, unknown
   dependencies, incompatible bounds or incomplete closure. Inactive requirements
   still need valid syntax and an explicit recorded exclusion reason.
6. Respect E5's proposed ceiling: eleven project pages, eight compatible sidecars
   per project, 2 MiB/page, 256 KiB/sidecar, 60-second overall deadline, no retries.
   Exceeding any ceiling rejects; do not raise limits without approval. The
   transport must enforce limits independently of parsing and prevent archive I/O.
7. E5 currently forbids persistent evidence/log/cache files. Agree an explicit
   exception and approved evidence destination before any persistent capture, or
   retain bounded in-memory evidence and label it insufficient for a durable lock.
   A future evidence record must include retrieval time/status/URLs, page-to-sidecar
   advertisement binding and digests, wheel filenames/index-advertised archive
   hashes (archive bytes NOT retrieved), target tags/markers, every dependency edge,
   exclusions, rejected candidates and exact tool/provider identities. Do not create
   duplicate reports. Metadata closure can establish only metadata consistency and
   advertised wheel eligibility, not artifact integrity, native loading, V17 parity
   or reproducibility. Package acquisition and installation remain separate stages.

## Platform and frozen-model gates

Required metadata checks: actual interpreter/build and Windows release/build;
complete supported tag set; Requires-Python for every candidate; target-marker
evaluation; matching wheel identity; full closure and wheel-variant consistency.
Later authorized native checks must establish Windows DLL/Visual C++/OpenMP runtime
requirements, CPU instruction support, NumPy/SciPy/sklearn/XGBoost binary interfaces
and required CPU/GPU mode. No native runtime versions are known here. Linux Docker
probe results/Python 3.12.15 cannot certify this Windows 3.12.7 environment. A venv
alone is not an execution boundary.

Reuse recorded frozen identities, without rereading/interpreting the model here:
model SHA-256 `e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98`;
source SHA-256 `afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3`.
Serialization protocol, producer joblib version, actual class references and
fitted-object compatibility remain unknown. Never import the training module:
it can attempt pip installation at import time, configure plotting/logging, and
its main path trains/runs a demo.

Source lines 200-231, 1351, 2699-2737 and 2846 onward specify the intended contract:
eight ordered categorical fields (Disease; Symptom Severity; Nadi Reading;
Constitution/Prakriti; Stress Levels; Sleep Patterns; Age Group; Physical Activity
Levels), followed by four numeric fields (BP Systolic; BP Diastolic; Pulse Rate;
Weight (kg)). Shared fitted ColumnTransformer uses dense OneHotEncoder with
handle_unknown=ignore, numeric passthrough, remainder=drop. Transform only: no
refitting or rebuilt vocabularies. Each selected target classifier predicts an
encoded class, decoded by its fitted label encoder into exactly four ordered
targets: Herbal Therapy Strategy; Lifestyle Recommendations; Therapeutic Yoga
Module; Follow-up Recommendation. Source intent is not verified bundle content.

Review actual fitted category/class order, matrix width/dtype, numeric conversion,
one-row prediction shape and four complete classifiers after separately approved
loading. Training normalization is not called by predict_single; do not add it
silently. Resolve unknown-category/spelling/case/whitespace policy. Reject missing,
extra, null, boolean, nonfinite or malformed inputs; preserve explicit zero. Source
numeric/category defaults, missing-target fallbacks and probability exception
swallowing cannot prove success. Raw transform/predict/decode parity needs a reviewed
independent driver. Enrichment, reasoning, confidence and manual prescription
placeholder are outside this four-label milestone.

## Unresolved decisions and evidence required for separate approvals

1. Approve or revise the eleven candidate versions and exact tooling baseline.
   Supply real wheel-sidecar metadata before calling any dependency resolved.
   Recover producer version/build/protocol evidence if available; otherwise attest
   that this is an experimental runtime, never original-runtime reproduction.
2. Select the exact Windows release/build, interpreter identity, CPU/native runtime
   and new disposable environment path. Provide target-tag and binary compatibility
   evidence; missing wheel support must stop, not trigger a platform/version change.
3. Supply and review the exact sidecar-only resolver/provider and complete parser/tag
   implementation. Approve bounded offline execution separately from network access;
   approve index and sidecar hosts, limits and durable evidence policy separately.
4. After metadata review, separately authorize acquisition/install/provisioning.
   Require a complete dependency selection, authenticated wheel identities, verified
   downloaded-byte hashes and installed inventory before later runtime acceptance.
   Metadata-only resolution cannot supply those installation proofs.
5. Confirm producer/artifact trust and serialization/class requirements. Resolve
   existing Step 1.3 NOT ACCEPTED boundary: independently enforced deadline,
   whole-worker/descendant termination and supervisor/VM-failure recovery; no
   secrets/data mounts/network, read-only artifact, bounded resources and diagnostics.
   Accept a Windows-appropriate boundary with harmless evidence before loading.
6. Authorize one load/structure-only attempt separately, bound to exact artifact,
   source, runtime and boundary identities. Verify and consume the same immutable
   model buffer; reject warnings, mismatches or missing fitted components without
   repair/refit/fallback. Loading-disabled scaffold remains unchanged by this plan.
7. Approve a reference protocol and typed input/four-label fixtures before inference.
   The archived op.txt demo is a candidate, not an approved oracle; decide explicitly
   whether its `Diabetes Mellitus Type 2` spelling is an accepted unknown-category
   case. Do not substitute `Diabetes Mellitus (Type 2)`. Require preprocessing
   intermediates, expected labels, driver/runtime/artifact/source identities and
   owner provenance/approval; one demo is insufficient broad parity coverage.
   Any new reference generation and inference need their own authorization.

Dataset provenance remains unresolved and does not permit selecting/replacing data
or retraining. Clinical policy, result release and endpoint integration remain
outside this environment plan. **Stop after this draft and await approval before
dependency resolution, provisioning or any execution.** This drafting session used
only local text/file inspection and audit-file hashing; no Python, imports, tests,
network/PyPI, pip/resolver, package download/install, model loading or inference.
