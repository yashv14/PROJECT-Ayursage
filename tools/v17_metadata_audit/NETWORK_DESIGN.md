# Future network adapter — documentation only

Client: ayursage-metadata-audit 0.2.0-proposed.

No HTTP implementation exists or is authorized.
All source and tests remain proposed and unexecuted.

## Synthetic provider milestone: static implementation, 14 October 2026

`SyntheticProvider` and `audit_index` now live in the existing `proposed.py`.
The original `audit(WheelFixture)` entry point remains the legacy synthetic
checker; its supplied compatibility Boolean is still untrusted. The new entry
point constructs that Boolean internally only after checking its explicit target
tag policy. It performs no I/O and accepts in-memory `SyntheticResponse` objects
only. No HTTP implementation, installer or general version-selection resolver is
added. Pip 24.2, vendored resolvelib 1.0.1 and packaging 24.1 remain recorded local
tooling evidence, not execution requirements or standalone installations. Fixed
candidate checking needs none of those libraries in this milestone.

### Synthetic index contract and policies

Each canonical approved project URL maps to status 200, the same final URL and
ASCII JSON bytes with exactly `meta={api-version: "1.0"}`, `name` and `files`.
Each file has exactly `filename`, an absolute HTTPS `url`, nonempty
`requires-python`, `yanked=false`, and `core-metadata={sha256: <lowercase digest>}`.
This is a restricted PEP 691-shaped fixture contract, not a general PEP 691/HTML
implementation. Other fields/formats/API versions, numeric values, duplicate JSON
keys, malformed JSON and missing evidence reject. All entries must identify the
approved project and exact candidate version. Source advertisements reject, rather
than being fetched or skipped. All yanked entries reject, including reason strings;
there is no exact-pin exception. After index parsing and bounded filename-key
checks, duplicate filenames reject before individual advertisement validation,
even if identical. The lexicographically first duplicate filename determines the
rejection evidence, independent of advertisement order.
Distinct compatible wheel/build variants are permitted only with equal supported
metadata signatures; conflicting signatures reject. Index and sidecar
Requires-Python clauses must match structurally, not merely be equivalent.

The provider derives `<advertised-wheel-url>.metadata`; the archive URL is used
only as an identity string and never as a response request. It binds each sidecar
to project/version/filename, exact project-page URL and raw page SHA-256. Only a
registered `BoundSidecarRequest` can look up that sidecar. Unbound sidecars, bare
URL strings, arbitrary request objects, archive/source/build/fallback responses
and unadvertised extra responses reject. URL validation rejects wrong hosts,
credentials, non-HTTPS/ports, queries, fragments and unsafe paths. A fixture hash
matches synthetic bytes only, never real PyPI provenance.

The explicit target policy includes cp312-cp312 and cp312-none on win_amd64;
cp32 through cp312 with abi3 on win_amd64; py3 and py30 through py312 with none on
any/win_amd64. Dot-compressed tag products are checked with at most eight tokens
per field. Filename grammar supports an optional numeric-leading build tag.
Other well-formed tags have no approved intersection; malformed/unsupported
filename forms reject. This policy is not measured host tags, wheel availability,
native ABI compatibility or proof of a complete real interpreter tag inventory.

Existing restricted version, requirement, marker and metadata parsers are reused.
Legal syntax outside that subset rejects without approximation. Every fixed
candidate is a root; all applicable requirements must name fixed candidates and
satisfy their versions. A visited-set recursive graph traversal bounds cycles to
eleven nodes. The shared traversal helper permits a single-root cycle test while
production still uses all eleven candidates as roots. Inactive dependencies are
recorded as TARGET_MARKER_FALSE; inactive
syntax/unknown marker variables still reject. No candidate selection, pruning,
automatic map expansion, builds, archive fallback or metadata stripping occurs.

### Bounds, evidence and acceptance definitions

Limits: eleven project pages, eight entries/page (including incompatible entries),
2 MiB/page, 256 KiB/sidecar, 99 total responses, 2048-character URLs,
256-character filenames and JSON nesting depth eight. The existing parser limits
also apply. Response maps are copied; input validation/processing is ordered by
URL/project/filename. Successful output is semantic and deterministic across
response-map and index-file order, with sorted graphs/exclusions/binding records.
Raw page hashes are retained internally in request bindings, not included in the
semantic result because byte ordering changes those hashes. Durable authenticated
retrieval evidence remains future work. This pure bounded parser has no measured
wall-time guarantee: an externally enforced execution deadline remains required.

`SyntheticIndexProviderTests` in the existing `test_proposed.py` defines binding,
mismatch, archive/type denial, tag policy, Requires-Python, yanked/ambiguity,
recursive/missing/conflicting dependencies, markers/unsupported syntax,
determinism, size/depth bounds, malformed input and failure cases. These definitions
express intended behavior; **none has been executed and no test pass is claimed**.
The success determinism test asserts both runs succeed before comparing serialized
results; duplicate rejection order has a separate test. Registered-binding tests
verify a valid lookup, then alter registry page-hash evidence and expect
UNBOUND_SIDECAR_REQUEST for the original request. This tests registry/request
equality, not tamper-proof storage. Single-root cycle assertions require actual
dependency traversal rather than merely returning the all-root candidate list.
Metadata duplicate checks cover Metadata-Version, Name, Version and Requires-Python
only; no general singleton-header enforcement is claimed.
Unexpected programming errors propagate; declared rejections expose no partial
successful binding evidence.

Only static source inspection and byte identity recording have occurred. Synthetic
behavior is implemented for review, not empirically proven. Real index parsing,
authenticated advertisements, complete tag verification, full PEP 440/508/core
metadata support, transport enforcement, native/model compatibility and
reproducibility remain unverified. Separate authorization is required for offline
fixture tests, any real metadata transport, package acquisition or model work.

The remaining sections describe legacy checker limitations and future real-network
requirements; the synthetic provider does not clear those requirements.

## Evidence boundaries

The offline client accepts synthetic fixtures only.
Successful fixture checks report "synthetic-only".
Declared validation failures report "incomplete/rejected".
Unexpected programming errors propagate.

The client cannot emit an independently verified real-resolution status.
A future independently verified status requires a separately reviewed evidence
producer, authenticated retrieval records, complete target-tag verification,
advertisement provenance and a complete dependency check.

Matching a supplied SHA-256 establishes fixture-byte integrity only.
It does not establish that PyPI advertised the sidecar.

Every fixed candidate is checked as a root.
Every applicable requirement is checked against the fixed candidate map.
Missing or unapproved dependencies and incompatible required versions reject.
The client does not choose versions, prune candidates or resolve alternatives.

## Restricted grammar

The implementation is not complete PEP 440/508 support.
Its module documentation defines the accepted subset.
Unsupported forms reject instead of being approximated.

Marker operator positions require an operator token.
Non-operator tokens, including membership words, reject as MALFORMED_MARKER.
Operator tokens outside ==, !=, <, <=, >, >= reject as
UNSUPPORTED_MARKER_OPERATOR.
String variables support equality/inequality only.
All Boolean branches are validated, including otherwise inactive branches.

Variant comparison is conservative: differing supported metadata rejects even
when requirements could be semantically equivalent.
Duplicate wheel filenames within a candidate's fixture list reject with
DUPLICATE_WHEEL_FILENAME, including entries flagged incompatible.
Non-duplicate compatible entries remain ordered by filename for evidence output.

## Proposed request policy

- Canonical https://pypi.org/simple/<normalized-project>/ pages only,
  restricted to the fixed CANDIDATES map.
- ProjectPageRequest rejects unapproved names during construction.
  Transport.fetch independently revalidates project approval before dispatch.
- An unapproved dependency is reported; it never causes a new project-page
  request or automatic expansion of the candidate map.
- Separately advertised PEP 658/714 wheel metadata sidecars.
- Proposed sidecar host: files.pythonhosted.org, HTTPS port 443;
  separate approval required.
- Reject redirects, credentials, unapproved hosts, direct/VCS requirements,
  archive retrieval, source distributions, builds and fallback retrieval.
- No caches, persistent logs or evidence files.

The adapter must prove that each exact sidecar URL and SHA-256 was advertised
by an approved project-page response.

SidecarRequest validates URL shape and hash syntax only.
It does not provide advertisement provenance.
The typed transport interface rejects archive-shaped requests, but a future
adapter still requires independent review to establish that it cannot bypass
the interface.

## Future wheel verification

- Parse actual filenames with a pinned, reviewed implementation.
- Match project/version to approved candidates.
- Generate the complete approved CPython 3.12 Windows AMD64 tag set.
- Check wheel tags and Requires-Python.
- Never treat WheelFixture.compatible as real verification.

WheelFixture.compatible is an untrusted synthetic test flag.
Synthetic filenames are placeholders, not verified wheel identities.
No actual wheel availability, native ABI compatibility or model compatibility
is established by the offline tests.

Windows release/build remains unresolved.
Markers depending on platform_release or platform_version reject.

## Proposed limits requiring approval

- 11 project pages; at most 8 compatible sidecars per project.
- 2 MiB project-page and 256 KiB sidecar response limits.
- 60-second overall deadline; no automatic retries.
- Exceeding a limit rejects rather than increasing it.

Offline input limits:
- Project name: 128 characters.
- Version string: 64 characters.
- Individual specifier bound: 64 characters.
- Specifier text: 4096 characters.
- Specifier clauses: 32.
- Metadata bytes: 256 KiB inclusive; one byte above rejects with
  METADATA_SIZE_OR_TYPE before hashing or parsing.

Oversized inputs produce stable declared rejections.
These limits also apply during metadata and requirement validation.
An outer metadata/requirement size limit may reject before a nested limit.

## Future offline execution restrictions

Test execution requires separate authorization and independent controls:
network denial, read-only source/fixtures, no credentials/model/patient data,
no child-process launch, bounded resources and an external deadline.

Use Python -B and a runner without file caches or report output.
The monkeypatch I/O tripwire is a regression test, not a sandbox.
It does not cover startup, imports or every operating-system I/O mechanism.

## Review identities

The original three review files' byte sizes and SHA-256 identities were verified
at Checkpoint 2. Those identities are historical and invalidated by the authorized
0.2.0 static edits. Current identities are recorded in the existing environment
manifest, not a new report. Static source review was performed without execution.
File identity verification and static review do not establish executed test
results or actual dependency resolution; neither later stage has been performed.
After an authorized edit, recompute SHA-256 over each file's exact bytes,
record byte lengths and bind subsequent review to all three identities.
Any source change invalidates that reviewed identity.

No package acquisition, installation, lock creation, model loading, training,
inference, worker launch or clinical release is authorized by this document.
