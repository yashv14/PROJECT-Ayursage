# AYUR-SAGE verification

## Phase 3 Step 1.3.5 focused verification - 12 October 2026

Decision: Step 1.3 NOT ACCEPTED. Heartbeat retry behavior was verified; independent
parent/child termination and a surviving real observer remain UNVERIFIED.

Changed files and reasons:

- infra/docker/worker_diagnostics.py: bounded Windows replacement retries retaining
  one timestamp; structured native-error/attempt context; expired-read rejection;
  pure termination-evidence validation for synthetic regressions.
- infra/docker/worker_diagnostic_audit.py: supported container-level wait/inspect
  in place of post-stop exec; later event cutoff; descendant flags remain false.
- tests/integration/test_heartbeat_publication.py (new): eight focused publication
  tests, including a real native Windows reader on an isolated temporary JSON file.
- tests/integration/test_termination_observation.py (new): ten synthetic/mocked
  identity/exit-observation tests, without Docker workers or PID descriptors.
- docs/setup/v17-loading-audit.md and this file: procedure, results and blockers.

The original native handle behind WinError 5 remains UNDETERMINED. A successful
retry does not establish that cause. Atomic publication remains; no direct-write
fallback or fresh timestamp on failure was added. The native fixture test opened
its own known reader handle without delete sharing and closed it before retry.
The published value remained unchanged during denial. Persistent errors, expired
retry/global deadlines, invalid data and incomplete evidence remain fail closed.

Verification order and exact commands:

```powershell
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/integration -p 'test_heartbeat_publication.py' -v
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/integration -p 'test_termination_observation.py' -v
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/integration -p 'test_worker*.py' -v
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
```

| Check | Executed result |
| --- | --- |
| Focused publication | Exit 0: 8 tests, 0.078s, OK; Windows native fixture included, no skips |
| Focused termination evidence | Exit 0: 10 tests, 0.001s, OK; synthetic/mocked only |
| Existing watchdog/diagnostic suites | Exit 0: 43 tests, 0.336s, OK |
| ML scaffold | Exit 0: 17 tests, 0.077s, OK |
| Phase 2 backend | Exit 0: 13 tests, 0.038s, OK |
| Dependency consistency | Exit 0: No broken requirements found |
| Targeted live Docker worker | SKIPPED: surviving observer and process mapping not validated |
| Complete watchdog audit | SKIPPED: targeted live evidence prerequisite unmet |

Publication coverage: success; transient replacement failure then success;
persistent replacement failure; retry-deadline exhaustion; expired pre-write
budget; noncandidate errors; publication completing after the global deadline;
concurrent native Windows read/delete-sharing denial. Replacement failures never
advance the accepted timestamp; late physical publication remains rejected by the
reader's global-deadline check. No unconditional filesystem runtime bound is claimed.

Observation coverage: both processes alive; simulated exits of both; wrong namespace
and boot; PID/start/PPID mismatch and reuse; observer failure/timeout; observer not
validated or not surviving; only one exit; container exit with no descendant
proof; container wait/inspect without post-stop exec; failed wait. These tests
validate supplied-evidence handling, not an actual Linux PID-descriptor collector.
No process observation mechanism surviving a real worker exit was validated.

Read-only inspection commands (both exit 0):

```powershell
docker context inspect desktop-linux
wsl -d docker-desktop --exec sh -c 'readlink /proc/self/ns/pid; readlink /proc/1/ns/pid; command -v python3; command -v python; command -v nsenter; cat /proc/sys/kernel/random/boot_id'
```

Context: npipe:////./pipe/dockerDesktopLinuxEngine. WSL shell and PID 1 reported
pid:[4026532219]; nsenter was /usr/bin/nsenter. No Python executable was returned
on that shell PATH. The host-Python capability check returned pidfd_open=false.
No namespace entry or observer provisioning was attempted. Earlier WSL absence
observations do not validate the Docker PID mapping, and no current worker was
created to establish one. A guardian is not provisioned; it would require a
separate test boundary and could not observe after its own container-wide KILL.

Persistent evidence is under reports/step-1-3-5-beeaf978742c/:
verification-results.json, observer-status.json, protected-before.json and
protected-comparison.json. Comparison confirmed all 16 protected file hashes
unchanged, including backend and dependency files, .env.example, root venv config,
checksum/loading-refusal modules, production model, V17 source and dataset.
Existing reports/fixtures were preserved. Docker/WSL operations were read-only;
no resources were created, started, stopped, restarted, deleted or pruned.
No packages, system settings, Flask routes or frontend files were changed. No
pickle deserialization, training-source execution or ML inference occurred.
The existing loading-refusal regression passed; loading remains disabled.


## Phase 3 Step 1.3.3 diagnostic test - 12 October 2026

Decision: Step 1.3 NOT ACCEPTED. One controlled harmless worker was executed and
its required post-termination evidence was inconclusive. No V17 execution occurred.

Created: infra/docker/worker_diagnostics.py,
infra/docker/worker_diagnostic_audit.py, tests/integration/test_worker_diagnostics.py.
Modified: infra/docker/worker_watchdog.py, infra/docker/worker_control_probe.py,
tests/integration/test_worker_watchdog.py, docs/setup/v17-loading-audit.md and this
file. Existing test fixtures now declare diagnostic completeness explicitly; all
29 prior watchdog tests are retained. Approval/checksum modules, backend, pins,
.env.example, model, training source and dataset were not changed.

Executed from the workspace root:

```powershell
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/integration -p 'test_*.py' -v
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
ml/.venv/Scripts/python.exe -B infra/docker/worker_diagnostic_audit.py
ml/.venv/Scripts/python.exe -B infra/docker/worker_control_audit.py
ml/.venv/Scripts/python.exe -B -m ml.inference.audit --load
```

Nonzero Python CLI checks used `exit $LASTEXITCODE` to preserve their exit codes.

| Check | Actual result |
| --- | --- |
| Final integration/diagnostic suite | Exit 0; 43 tests in 0.444s, OK (29 existing +14 new) |
| ML scaffold | Exit 0; 17 tests in 0.089s, OK |
| Backend | Exit 0; 13 tests in 0.105s, OK |
| pip check | Exit 0; No broken requirements found |
| Routes | Exit 0; GET /api/health only |
| Single controlled diagnostic worker | Exit 1; inconclusive, accepted=false |
| Basic harmless worker-control audit | Exit 0; controls 0, intentional failure 7, timeout 137 |
| Loading refusal | Exit 2; LOADING_DISABLED_PENDING_REVIEW; execution flags false |

Initial diagnostic test discovery included an imported TestCase twice (58 executed
checks); that duplicate discovery was removed. The subsequent unique suite passed
42 tests; bounded-publication coverage and stricter diagnostic gates passed the
final 43. No inflated initial count is treated as independent coverage.

Controlled evidence: reports/worker-diagnostic-266386ea39c0/. Container ID
244f09e2a915afb8e5b893fbe61502bd6f70850921985fd42295e05d0c3b4217,
name ayursage-controls-diagnostic-2f1cf78cafcb. Exact restrictions/labels were
inspected before start and KILL and after exit. Only fixture/probe mounts were used.
The separate publisher PID was 24976, reader PID 20996. Both reported the Windows
GetTickCount64() host clock. Heartbeat logs contain 38 writes (37 successes and one
PermissionError) and 121 valid reads. Exact retained timing:

| Event | Host monotonic seconds | Source |
| --- | --- | --- |
| Last successful publication | 23669.859 -> 23669.859 | heartbeat-writer.jsonl |
| Failed replacement, WinError 5 | 23669.953 -> 23669.953 | writer JSONL and writer-stderr.log |
| Overlapping successful read, value 23669.859 | 23669.953 -> 23669.953 | heartbeat-reader.jsonl; age 0.094s |
| First stale read | 23672.906 -> 23672.906 | reader JSONL; value 23669.859, age 3.047s, threshold 3s |
| Fresh inside parent/child observation | 23681.656 -> 23683.406 | fresh-precondition.json |
| KILL request/return | 23683.406 -> 23683.843 | kill.json; exit 0 |
| Stopped state inspection | 23683.859 -> 23684.156 | config-after-kill.json; exit 137 |
| Post-termination exec attempt | 23684.156 -> 23684.468 | post-observation.json; exit 1, not running |
| Completion receipt | 23685.203 | completion.json; publisher exit 1 |

Windows clock resolution is approximately 15.625ms; equal-tick overlap does not
prove a particular native handle caused the access denial. The new publication
failure and subsequent stale values are established; the historical cause remains
UNDETERMINED. Reader ages ranged from 0 to 11.062 seconds after publisher exit.
Diagnostics_complete=false includes the failed publisher, even though its logger
successfully drained (heartbeat-writer-status.complete=true). No read/parse error
was observed in this live test; those paths were exercised deterministically.

Inside initial/fresh observations matched PID 1 and child 8, PPID relationship,
start ticks 9218/9262, boot ID and namespace pid:[4026532383]. Both were alive in
the fresh observation, and KILL began in the observation's completion clock tick.
Docker inventory showed 439/453. The WSL process query showed ABSENT:439/453;
its namespace query failed with BusyBox usage output, despite overall shell exit 0.
It is inconclusive, not a validated namespace comparison. The command was fixed
for future runs. The later supplemental read-only query used individual readlinks,
exited 0 and recorded boot 293da8cc-ab9c-44d4-9aa0-c683fbef1937 and namespace
pid:[4026532219]. Its changed boot ID prevents retrospective correlation. No
cause of that boot-ID difference is inferred, and no system change was performed.

Docker state records StartedAt 10:34:26.044430433Z and FinishedAt
10:34:42.494996908Z. Events captured start, exec observations and signal-9 KILL;
a die event was not retained by the query ending at FinishedAt. Post-termination
inside observation was unavailable because the container had exited. Therefore
parent_termination_verified=false, child_termination_verified=false and
recovery_required=true. Elapsed 19.235s was within the diagnostic 35s budget,
but this is not a watchdog deadline-enforcement pass. The final result checksum
matched its receipt; independent evidence review retained these rejected flags.

Exactly one controlled diagnostic worker was run. The requested basic audit also
created three harmless control/failure/timeout workers, retaining all resources:
reports/worker-controls-985833538668/results.json. Durations were 1.531s, 1.563s,
6.609s respectively. Its five-second timeout trigger is not a hard completion bound.
Full four-scenario watchdog reruns, daemon-loss and privileged namespace-observer
experiments were not executed. No new approved descendant termination is claimed.

The BusyBox compatibility fix, bounded raw-command publication wait and final
stricter logging/heartbeat-error acceptance gates were applied after the single live diagnostic;
their coverage is static/deterministic, not a second live pass. The existing
single-result/receipt protocol and all mandatory rejection conditions remain.
Missing diagnostic completeness now also fails scenario acceptance. Bounded logging
does not establish an unconditional bound on final record/heartbeat filesystem I/O,
legacy journals, Docker/WSL scheduling or failure recovery.

Safety evidence: reports/diagnostic-checks-264b5032d0bb/ contains inventories, SHA-256
comparison and evidence-review.json. All 16 protected file hashes matched; all 19
pre-existing container IDs/names/states were preserved. Final inventory: 23 retained
containers, none running. No deletes, prunes, restarts, package installs, daemon
shutdowns or Windows/WSL/Docker configuration changes occurred. All generated
persistent evidence is under ignored reports/; generated-files.json lists it.
The frozen artifacts were read only as opaque bytes for checksum verification.
No deserialization, training-source import/execution or inference occurred.


## Phase 3 Step 1.3.1 corrections - 12 October 2026

Decision: Step 1.3 NOT ACCEPTED. The acceptance/completion defects were corrected;
real descendant verification failed closed. Earlier Step 1.3 success statements
below are historical and do not establish acceptance under this protocol.

Changed files: infra/docker/worker_watchdog.py,
tests/integration/test_worker_watchdog.py, docs/setup/v17-loading-audit.md and
this file. The worker-control audit/probe, ML scaffold and Phase 2 files were not
changed. Added 16 regression tests (29 watchdog tests total).

Commands executed from the workspace root:

```powershell
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/integration -p 'test_*.py' -v
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
ml/.venv/Scripts/python.exe -B infra/docker/worker_watchdog.py
ml/.venv/Scripts/python.exe -B infra/docker/worker_control_audit.py
ml/.venv/Scripts/python.exe -B -m ml.inference.audit --load
```

For nonzero CLI checks PowerShell used `exit $LASTEXITCODE` to preserve the actual
Python exit code. The initial load-refusal call printed the same refusal but the
shell wrapper returned 1; explicit propagation confirmed Python exit 2.

| Check | Actual result |
| --- | --- |
| Final watchdog suite | Exit 0; 29 tests, 0.256s, OK |
| ML scaffold suite | Exit 0; 17 tests, 0.075s, OK |
| Backend suite | Exit 0; 13 tests, 0.049s, OK |
| pip check | Exit 0; No broken requirements found |
| Routes | Exit 0; GET /api/health only |
| Corrected real watchdog audit | Exit 1; audit_accepted=false |
| Harmless worker-control audit | Exit 0; controls 0, intentional failure 7, timeout 137 |
| Loading refusal | Exit 2; LOADING_DISABLED_PENDING_REVIEW; all execution flags false |

The initial 25-test watchdog run failed with 13 temporary-directory permission
errors in the execution sandbox. An approved rerun passed 25 tests. Subsequent
coverage additions passed 28 tests and then the final 29 above. No package install
was used to fix test execution. No tests execute a pickle or the training source.

New tests cover every missing required field, late and contradictory flags,
malformed values, expected nonzero worker exits, no-replacement publication,
preliminary/missing/conflicting results, watchdog handle/exit/identity, completion
receipt timing, raw descendant observations, absent-before observations, Created
recovery, stopped containers lacking descendant evidence, and coordinator watchdog
crash/stall fallback. Recovery failures use deterministic fault injection; the
base-interpreter PID test launches a real harmless process.

Evidence: reports/watchdog-fad7e10e7ffd/results.json.
Normal controls: watchdog exit 0, supervisor exit 0, result elapsed 9.328s,
completion 9.828s, accepted. Timeout: worker exit 137, watchdog exit 1, supervisor
exit 0, result elapsed 24.609s, completion 24.718s, rejected. Its reason was
supervisor_unresponsive (event 22.734s), not the expected deadline_reserve.
The precise heartbeat delay cause is unresolved. Descendant-before.json observed
Docker PIDs 481/494, but the WSL observation already reported both ABSENT. After
termination they were still ABSENT; this is not proof of disappearance. The
container stopped, but required descendant termination remains unconfirmed.
Fallback also retained recovery_required. The audit exited 1 from final acceptance,
not successful completion of worker processes. Crash/unresponsive live scenarios
were not reached after this failure; no new live pass is claimed for them.
The final additional strict gates were applied read-only to saved results:
normal=true, timeout=false; both result hashes matched completion receipts.

Both live scenarios verified launcher/self identity. Raw diagnostic reproduction
and historical uncertainty are explained in v17-loading-audit.md. Records:
reports/step-1-3-1/identity-diagnostic.json and evidence-review.json.

Evidence: reports/worker-controls-d71fdfe66262/results.json.
Controls elapsed 2.390s, failure 1.547s, timeout 6.000s. The older simple audit's
5-second trigger still is not a hard 5-second completion bound. Its successful
exit verifies its basic assertions, not the new watchdog acceptance protocol.

Docker containers were inspected read-only before operations. Final `docker ps -a
--format '{{.Names}} {{.State}}'` exited 0: 19 retained containers, 17 Exited and
2 Created, none Running. Five harmless containers were created this step. No
existing resources were restarted, deleted or pruned, and no daemon/system
configuration changes were made. Real daemon-loss recovery, simultaneous
coordinator/watchdog failure, and unconditional deadlines remain UNVERIFIED.

SHA-256 comparisons in reports/step-1-3-1/protected-comparison.json confirm all 16
baseline protected files unchanged: backend Python/dependency files, .env.example,
root venv config, checksum/audit modules, production model, source and dataset.
Model/source approved-hash regression tests also passed. No deserialization,
training-source execution, ML dependency installation or prediction route occurred.
All generated reports/fixtures are ignored by the existing reports/ rule.
reports/step-1-3-1/generated-files.json lists generated persistent evidence files.


## Phase 3 Step 1.3: independent watchdog — 12 October 2026 (Asia/Calcutta)

### Files and scope

Added `infra/docker/worker_watchdog.py` and
`tests/integration/test_worker_watchdog.py`. Refactored the fixed harmless worker
creation in `infra/docker/worker_control_audit.py` to share its restrictions and add
audit ownership labels. Updated the loading procedure and this record. Probe,
checksum/loading-refusal modules, backend, frontend and dependency files unchanged.

Initial read-only Docker inspection confirmed the five Step 1.2 containers were
Exited or Created, with none Running. They were not deleted or restarted. No Docker
service, WSL configuration, image, volume or unrelated container was changed.

### Executed commands and results

```powershell
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/integration -p 'test_worker_watchdog.py' -v
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
ml/.venv/Scripts/python.exe -B infra/docker/worker_watchdog.py
ml/.venv/Scripts/python.exe -B -m ml.inference.audit --load
ml/.venv/Scripts/python.exe -B infra/docker/worker_watchdog.py recover reports/watchdog-bc76ad97f5c1/complete
```

| Check | Actual result |
| --- | --- |
| Final deterministic watchdog suite | Exit 0: 13 tests in 0.022s, OK |
| ML checksum/buffer suite | Exit 0: 17 tests in 0.069s, OK |
| Phase 2 regression suite | Exit 0: 13 tests in 0.046s, OK |
| Backend dependencies | Exit 0: No broken requirements found |
| Flask routes | Exit 0: /api/health only |
| Final real harmless watchdog audit | Exit 0: four explicit scenario assertions passed |
| Loading refusal | Exit 2: LOADING_DISABLED_PENDING_REVIEW; no model loaded/executed |

Fault injection uses a virtual monotonic clock and simulated worker state, without
Docker or model access. Cases cover timely completion, long worker/child termination,
unresponsive supervisor, slow termination, startup/cleanup overruns, capture failure,
daemon unavailability, stale recovery and unrelated ownership labels. A pending-startup
regression prevents premature kills. Late cleanup remains deadline_exceeded even if
the worker is stopped. Unconfirmed daemon-loss termination is never accepted.

### Measured real scenarios

Evidence: `reports/watchdog-e534718b05a8/results.json`, with per-scenario manifests,
event journals, state, process inventory and separate worker/supervisor/watchdog logs.
Only the harmless probe and disposable fixture were mounted into restricted containers.

| Scenario | Full measured duration | Worker exit | Supervisor exit | Result |
| --- | --- | --- | --- | --- |
| Normal control probe | 1.813s | 0 | 0 | Deadline met; controls passed |
| Overlong worker and child | 26.891s | 137 | 0 | Stopped using termination reserve; deadline met |
| Real supervisor crash | 5.703s | 137 | 23 | Independent watchdog detected stale heartbeat and confirmed termination |
| Unresponsive supervisor | 5.891s | 137 | 1 | Independent watchdog recovered worker; coordinator subsequently terminated only its stalled host supervisor |

Start: monotonic timestamp before manifest publication/supervisor launch, including
creation and startup. Budget: 35 seconds, termination reserve begins at 25 seconds.
End: after stopped-state verification, stdout/stderr/state capture and first result
publication. Final timing annotation and subsequent separate stale-run reinspection
are excluded. Cleanup means finalized evidence and stopped worker; containers,
fixtures and reports are deliberately retained. No deletion is required for a pass.

The watchdog is a separate host process started by the supervisor before worker
creation. Crash uses os._exit(23), not a mocked failure or replacement worker. The
worker remains a restricted Docker container. Parent/child host PIDs were observed
and WSL /proc absence checks exited 0 after termination: timeout 920/934, crash
1001/1014, unresponsive 1081/1094. All container states were stopped, Pid 0, and
label-scoped stale reinspection confirmed termination without restart/deletion.

### Failures retained and honest limits

First real run, reports/watchdog-bc76ad97f5c1, exited 1: create command timed out.
Watchdog measured 20.235s against the initial 15s budget and correctly reported
deadline_exceeded, termination_unconfirmed and recovery_required. A Created worker
was retained; a later recovery inspection remains unconfirmed because lifecycle
completion evidence is missing. Docker remained responsive; no model startup occurred.

Second diagnostic run, reports/watchdog-12ffb84a1c77, exited 0 at the harness level
but its scenarios are NOT accepted as evidence: startup observation raced creation
and killed workers prematurely (all worker exits 137; intended crash did not happen).
Fixed startup readiness and added explicit expected exit/reason assertions, plus the
deterministic regression. The final run above passed these corrected assertions.
All nine Step 1.3 workers and all five original workers are retained, none Running.

Real Docker-daemon loss was not induced, because stopping Docker Desktop could
disrupt unrelated work. Only fault-injected daemon-loss handling is tested. Recovery
attempts fail closed and persist uncertainty; no independent VM termination fallback
has been provisioned. A strict deadline under arbitrary OS/daemon stalls is still
UNVERIFIED. Successful 35-second-budget samples do not prove an unconditional bound.
Evidence writes use atomic replacement but do not promise disk survival after host
power loss. Supervisor/watchdog simultaneous failure remains untested.

No model/training-source execution, deserialization, package installation, resource
deletion or system-setting change occurred. Model, source, dataset, .env.example,
backend/dependency files and root environment config were compared with the prior
SHA-256 manifest. Independent approved-hash tests passed unchanged. Loading remains
disabled; no loading authorization is requested or assumed.

## Phase 3 Step 1.2: restricted worker investigation — 12 October 2026 (Asia/Calcutta)

### Actual environment and actions

Read-only registry inspection: CoreSingleLanguage, build 26300, DisplayVersion
26H2; legacy ProductName Windows 10 Home Single Language. WSL reports Windows
10.0.26300.9457. WSL 2.7.10.0, kernel 6.18.33.2-2; docker-desktop registered with
version 2, initially stopped. hns, vmcompute and WslService running. Docker Desktop
is installed per-user at AppData/Local/Programs/DockerDesktop; no com.docker.service
entry was found. WindowsSandbox.exe and workspace .devcontainer are absent.
No configuration was recreated, deleted, edited or feature enabled.

Sandbox WSL status/list initially failed with E_ACCESSDENIED; approved read-only
retry succeeded. Docker Desktop CLI status reported starting. The authorized
`docker desktop start --timeout 30` returned exit 0, already running. Subsequent
daemon inspection succeeded: Docker Desktop 4.93.0, Engine 29.8.1 linux/amd64,
WSL2 kernel 6.18.33.2-microsoft-standard-WSL2, overlayfs, cgroup v2. AutoStart false.
No reinstall, WSL update, system-setting change or Docker resource deletion ran.

### Harmless control test

Created `infra/docker/worker_control_probe.py` and
`infra/docker/worker_control_audit.py`. Updated the procedure and this record.
No Phase 2, checksum or loading-boundary module was edited. The supervisor can run
only the fixed harmless probe; it mounts that probe and a disposable fixture,
never models, training source, dataset or the whole workspace. It retains workers.

Used the already present official Python image:
`sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`.
Image metadata reports Python 3.12.15, not the training metadata's 3.12.7. No image
download/build, package installation or runtime-compatibility claim occurred.

Executed with approved Docker access:

```powershell
wsl --status
wsl --list --verbose
wsl --version
docker desktop status
docker desktop start --timeout 30
docker version
docker info
docker image ls
docker ps
ml/.venv/Scripts/python.exe -B infra/docker/worker_control_audit.py
ml/.venv/Scripts/python.exe -B -m ml.inference.audit --load
```

First audit attempt exited 1 before the worker ran: local logging driver requires
compression disabled when max-file is 1. Second attempt exited 1 at the environment
allowlist because Docker automatically supplies HOSTNAME; earlier probe assertions
had completed. Added compress=false and permitted this non-secret container field.
The third complete audit exited 0. All five created workers, including unsuccessful
attempts, are retained; no existing resources or volumes were removed.

Evidence directory: `reports/worker-controls-1e4f8330e3ad/` (ignored). Includes
results.json, container state/exit status, stdout/stderr logs and observed process
list. No binary buffers, patient inputs or clinical results are logged.

| Check | Actual result |
| --- | --- |
| Control worker | Exit 0; audit elapsed 1.688s |
| Explicit read-only mounts | Exactly fixture.txt and probe.py; writes denied; root writes denied |
| Scratch | Separate tmpfs, non-root uid 1000; write/read succeeded |
| Network | NetworkMode none, only lo interface, no default route; external TCP and UDP port-53 transport returned ENETUNREACH |
| Environment/socket | Only allowlisted image/test environment keys; no Docker socket; no unrelated mounts or ports |
| Failure status/log capture | Intentional exit 7, elapsed 1.625s; distinct stdout/stderr captured |
| Timeout worker | Parent and child observed; killed container exited 137, Running false, Pid 0; docker top subsequently refused stopped worker; WSL /proc/638 and /proc/651 both absent |
| Timeout precision | Configured 5s; container StartedAt-to-FinishedAt about 6.070s; total audit elapsed 7.437s including state/log collection |
| Hard deadline | NOT VERIFIED: polling and synchronous Docker command latency permit overshoot |
| Supervisor crash/daemon loss | NOT TESTED; independent watchdog/VM recovery not implemented |
| Loading refusal | Process exit 2; model_loaded and inference_executed false |
| Protected files | SHA-256 manifest equals prior review for backend Python files, dependency pins, .env.example, root venv config, model, source and dataset |

The network probe tests outbound transport to documentation address 192.0.2.1,
including UDP port 53; it does not claim DNS resolver behavior or disabled loopback.
No real model/source mounted or executed. Resource bounds and no-new-privileges
were configured/inspected; resource-exhaustion and kernel-escape testing was not done.
Final read-only `wsl --list --verbose` confirmed docker-desktop Running, version 2.
`wsl -d docker-desktop --exec ls -d /proc/638 /proc/651` returned no such directory
for both observed parent/child host PIDs (ls exit 1, expected for absent processes).
`docker ps -a --filter name=ayursage-controls-` confirmed all five test workers
retained, with no Running workers. The exact resource IDs are in the audit report.

Docker availability is resolved without a system change, and basic worker controls
are demonstrated. Loading remains blocked on the independent watchdog/deadline and
failure-recovery evidence, approved dependency runtime and loading approval. Do not
substitute an ordinary Python process. No model loading or inference occurred.

## Phase 3 Step 1.1: review corrections — 12 October 2026 (Asia/Calcutta)

Scope: independent approved-hash assertions, retained-byte verification only, and
a concrete future restricted-worker design. No deserializer, inference callable,
package installation, source execution or Flask integration was added.

### Actual changes

- `ml/inference/checksums.py`: frozen VerifiedArtifact checks the digest of its
  immutable byte buffer; read_verified_file reads once; verify_workspace_buffers
  returns both retained objects only after both checks succeed. Existing metadata
  interfaces remain available and cannot authorize loading.
- `ml/inference/audit.py`: holds verified buffers and constructs metadata from them;
  loading requests are still refused unconditionally after verification.
- `tests/ml/test_loading_scaffold.py`: two unpatched literal-hash tests and five
  retained-buffer tests, including replacement after a single read, immutable data,
  rejection of mutable/wrong bytes and retention of both verified artifacts.
- `docs/setup/v17-loading-audit.md`: explains the byte boundary and documents
  concrete Docker worker arguments, supervision, logs and unresolved prerequisites.
- This verification record: executed evidence only. No new source file was needed.

### Commands and results

```powershell
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
ml/.venv/Scripts/python.exe -B -m ml.inference.audit
ml/.venv/Scripts/python.exe -B -m ml.inference.audit --load
```

| Check | Actual result |
| --- | --- |
| Non-loading ML suite | Exit 0: Ran 17 tests in 0.091s, OK; approved temporary-fixture access |
| Phase 2 suite | Exit 0: Ran 13 tests in 0.070s, OK |
| Backend dependency consistency | Exit 0: No broken requirements found |
| Route discovery | Exit 0: api.health, GET, /api/health only |
| Real artifact verification | Exit 0: both approved hashes match; model_loaded and inference_executed false |
| Loading refusal | Process exit 2: LOADING_DISABLED_PENDING_REVIEW; explicitly captured LASTEXITCODE |
| Independent-hash mutation checks | Exit 0: changing each hash to zeros in memory caused its literal test to fail as expected; constants restored; no file mutation |
| Preservation | Exit 0: backend Python files, both requirement files, .env.example, root .venv config, model, source and dataset hashes equal prior-review manifest; audit .venv config also unchanged |

The mutation experiment imported only the reviewed test/scaffold modules, patched
each production digest in memory using dataclasses.replace and unittest.mock.patch,
ran the corresponding ApprovedHashTests case and asserted exactly one expected
failure with no errors. These intentional failures demonstrate detection; the full
17-test suite passed with the actual approved constants.

The path-replacement test used non-serialized temporary bytes, not the real model.
It replaced the fixture immediately after Path.read_bytes returned, asserted exactly
one read, retained the original verified buffer, blocked reopening during buffer
consumption and confirmed subsequent verification rejected the replaced file.
Future deserialization is still absent: this tests the buffer abstraction, not a
loader's use of it. Read-only real-file checks never execute model/source contents.

### Windows inspection and limits

Executed Get-ComputerInfo, Get-Command, Get-Service, Test-Path for
WindowsSandbox.exe, registry OS metadata inspection and docker version. Docker CLI
29.8.1 is present; context desktop-linux, Server null. docker version exited 1
because dockerDesktopLinuxEngine named pipe was not found. hns and vmcompute are
running; WindowsSandbox.exe absent. Registry reports CoreSingleLanguage, build
26300, DisplayVersion 26H2 with a legacy Windows 10 ProductName label.

No daemon was started, feature enabled, container/image provisioned or restriction
tested. The documented Linux-container plan is an experimental portability target;
Windows training-runtime reproduction requires a separate approved Windows worker.
Network denial, read-only mounts, credential exclusion, scratch isolation, deadline,
whole-worker termination and logs must pass harmless provisioning tests before any
loading attempt. Daemon-failure termination needs a tested worker-VM teardown path.
The current venv is not a security sandbox. Original dependency versions, approved
reference cases and training-dataset provenance remain unresolved. Loading is disabled.

## Phase 3 Step 1: isolated verification scaffold — 12 October 2026 (Asia/Calcutta)

Only the checksum utility, disabled-loading scaffold, non-loading tests and audit
procedure were implemented. There is no deserializer or inference callable in the
new modules, and nothing is imported into Flask. The historical Phase 2 record
below remains evidence for that earlier scope, not the current copied-file inventory.

### Changes

- `ml/inference/checksums.py`: standard-library opaque-byte hashing against fixed
  approved model/source digests; missing, unreadable and mismatch errors.
- `ml/inference/audit.py`: verification-only CLI; successful checksums never enable
  loading. `--load` is an explicit refusal test, not an enable flag.
- `tests/ml/test_loading_scaffold.py`: ten tests using temporary non-serialized bytes.
- `docs/setup/v17-loading-audit.md`: recorded versus experimental dependencies,
  proposed restricted execution and unresolved evidence. This procedure has not
  been provisioned or executed and is not approval to install/load.
- Checklist records partial Phase 3 progress without completing the phase.
- Ignored `ml/.venv/` created with `--without-pip`; root `.venv` preserved.

### Executed checks

```powershell
python --version
python -m venv --without-pip ml/.venv
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
ml/.venv/Scripts/python.exe -B -m ml.inference.audit
ml/.venv/Scripts/python.exe -B -m ml.inference.audit --load
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

| Check | Actual result |
| --- | --- |
| Audit environment creation | Exit 0, Python 3.12.7; system-site-packages false; no pip found |
| New non-loading suite | Approved retry exit 0: Ran 10 tests in 0.149s, OK |
| Real-file checksum verification CLI | Exit 0, CHECKSUMS_VERIFIED_LOADING_DISABLED; model_loaded and inference_executed false |
| Explicit loading request | Exit 2, LOADING_DISABLED_PENDING_REVIEW; no deserializer invoked |
| Phase 2 regression suite | Exit 0: Ran 13 tests in 0.071s, OK |
| Existing backend dependency check | No broken requirements found |
| Flask route discovery | api.health, GET, /api/health only |
| Preservation checks | Before/after SHA-256 comparison passed for both backend requirement files, root .venv/pyvenv.cfg, production model, original source and dataset |

The real-file verifier read only opaque bytes: model size 13,023,934 bytes and
source size 190,567 bytes. Approved model/source hashes are fixed in checksums.py.
No training-source import, extraction, older audit/parity-script execution,
deserialization, inference or package installation occurred.

Initial new-suite execution failed: temporary-file writes and cleanup under the
host Temp directory were denied by the sandbox (10 tests, 20 setup/cleanup errors).
The approved retry ran the same suite successfully; no code change was needed.
Tests create only disposable non-serialized fixtures and do not touch real artifacts.

Existing ignore rules `.venv/`, `*.pkl`, `*.csv`, `data/` and `ml/artifacts/*` cover
the new environment and copied binaries/data. No ignore edit was needed. There is
still no Git repository, so tracked-file status is not established.

Dataset training-run provenance, complete original dependency versions, current
runtime compatibility, approved reference fixtures and successful inference remain
unverified. Network isolation/read-only worker mounts/deadline enforcement are
documented future requirements, not checks performed here. Step 1 implementation
is tested; review/approval is required before dependency installation or loading.

## Phase 2 backend foundation — 12 October 2026 (Asia/Calcutta)

The user explicitly authorized Phase 2 with a narrower scope than the original
checklist: Flask foundation only. Earlier Phase 1 evidence below is historical;
its outstanding container acceptance has not been marked complete.

### Inspection and scope

All project source files and reserved directories were inspected, including the
architecture, implementation checklist, verification record, README, backend
requirements and input requirements, environment template, ignore rules, frontend
package/lockfile presence and ML artifact instructions. Existing source consisted
of dependency/configuration documentation; there was no application or test code.
No applicable AGENTS.md was found in the workspace or ancestor directories.
The workspace has no Git repository and `.devcontainer/` is currently absent,
despite the historical Phase 1 record. Existing frontend dependencies/cache and
debug.log were left untouched. No V17 model artifacts were found or created.

### Implemented

- Application factory: `backend.app.create_app`, with isolated configuration per app.
- Environment configuration: process environment only; no automatic `.env` loading,
  no secret fallback. Reads `SECRET_KEY`, `FLASK_DEBUG` and `BACKEND_PORT`.
  Blank port defaults to 5000; invalid debug/port values fail without echoing values.
- API blueprint: `GET /api/health` returns HTTP 200 JSON `{"status":"ok"}`.
  This is liveness, not database, storage or inference readiness.
- JSON HTTP errors preserve status/headers; production-mode unhandled errors return
  a generic 500 response while Flask logs the exception.
- Local entry point: `python -m backend`, binds to loopback and reads BACKEND_PORT.
- 13 unittest tests in the existing `tests/backend/` directory. No new dependencies;
  both existing backend requirement files are unchanged.

Factory and HTTP error patterns were checked against the official
[Flask factory documentation](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)
and [Flask error documentation](https://flask.palletsprojects.com/en/stable/errorhandling/).

### Executed results

Commands ran from the workspace root using a new ignored project-local `.venv`:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m flask --app backend.app routes
.venv/Scripts/python.exe --version
```

| Check | Actual result |
| --- | --- |
| Isolated environment creation | Approved retry exited 0 |
| Existing pinned dependency installation | Approved retry exited 0; all seven pinned packages installed |
| Backend suite | Exit 0: Ran 13 tests in 0.057s, OK |
| Dependency consistency | No broken requirements found |
| Factory discovery / route listing | Successful; api.health, GET, /api/health; no other routes |
| Runtime | Windows host Python 3.12.7, Flask 3.1.3 |
| Container verification | Not performed; Docker daemon pipe unavailable; .devcontainer absent |

The suite verifies health JSON/status, JSON 404, JSON 405 with Allow header,
generic 500 with server logging and no private detail in the response, safe/blank
defaults, environment loading, valid/invalid debug values, invalid ports,
independent factory configuration, only the health route registered, and entry
point use of the configured port. HTTP responses were exercised through Flask's
test client; a live network server was not started. The entry point uses a mocked
server run call in its test. No claim of a live HTTP or container smoke test is made.

Initial failures: sandboxed venv creation failed during ensurepip (exit 1), leaving
an incomplete environment; its pip invocation reported no module named pip.
The approved environment-creation retry succeeded. Sandboxed dependency resolution
then reported no matching blinker distribution; approved installation succeeded.
Docker image inspection failed with the DockerDesktopLinuxEngine pipe not found.
No Docker workaround, image build or container recreation was performed.

Phase 2 is verified locally within this scope. SQLAlchemy/MySQL integration, JWT
patient/doctor/admin authorization, models, migrations, patient functionality,
reports, cloud storage, V17 inference, retraining and deployment were not implemented
or tested. Existing future-module folders remain reserved. No frontend build or
ML/integration suite was run because those directories contain no application/tests.
Phase 3 has not begun. Phase 1 container acceptance remains unresolved.

## Historical Phase 1 verification

Session dates: 10-11 October 2026, Asia/Calcutta.
Workspace: `C:\Users\yvasa\Videos\PROJECT-Ayursage`, explicitly approved by user.

## Results

| Criterion | Actual result |
| --- | --- |
| Workspace verified | Pass: Get-Location returned the approved path |
| Directory structure | Pass: all requested directories created and enumerated |
| Foundation files | Created and inspected; user review pending |
| Container image build | Pass: docker build exited 0 |
| VS Code Reopen in Container | Final check 11 October: not confirmed; Docker returned no running containers and no workspace-labelled stopped containers; UI inspection unavailable |
| Container runtimes | Python 3.12.15, Node 24.21.0, npm 11.19.0 |
| Backend clean install | Pass: exact requirements installed in the combined Linux image |
| Backend dependency check | Pass: pip check returned No broken requirements found |
| Backend CLI | Pass: Flask 3.1.3 / Werkzeug 3.1.9 |
| npm lockfile | npm-generated v3; direct dependencies match package.json |
| Windows npm ci | Pass: 21 packages installed, exit 0 |
| Linux npm ci | Pass: 21 packages installed in temporary container storage, exit 0 |
| Frontend tool | Pass: Vite 8.3.4 CLI ran on Linux with Node 24.21.0 |
| Isolation | Pass: uid/gid 1000 developer; no Docker socket; read-only workspace mount during validation |
| Environment template | Pass: comments and empty NAME= entries only |
| Git ignore rules | Reviewed for secrets, environments, data, model artifacts and generated output; no Git repository initialized |
| Existing files and volumes | Existing debug.log left untouched; no existing volumes mounted or deleted |
| Model compatibility | Unverified: V17 artifacts and dependency contract absent |

Phase 1 implementation and container checks are complete, but full acceptance is
pending actual VS Code reopening and user review. Phase 2 has not begun.

## Final verification attempt — 11 October 2026 (Asia/Calcutta)

Scope: verification only. Only this record was edited; no dependencies installed,
architecture changed, containers started or Phase 2 work performed.

The initial `docker ps` was denied by the sandbox at
`npipe:////./pipe/dockerDesktopLinuxEngine`. Approved read-only retries ran:

```powershell
docker ps --format '{{.ID}} {{.Names}} {{.Image}}'
docker ps -a --filter 'label=devcontainer.local_folder=C:\Users\yvasa\Videos\PROJECT-Ayursage' --format '{{.ID}} {{.Names}} {{.Status}} {{.Image}}'
Get-Process Code -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | Select-Object MainWindowTitle
Get-Item frontend/package-lock.json,backend/requirements.in,backend/requirements.txt | Select-Object FullName,Length
```

Both Docker queries exited 0 with no entries in the current Docker context.
The process query returned no VS Code main-window title. Computer-use inspection
and its retry failed with: `Computer Use native pipe is unavailable: failed to
connect native pipe: The system cannot find the file specified. (os error 2)`.
Therefore VS Code connection to the configured Dev Container cannot be confirmed.
No terminal commands were run in VS Code or in an attached container this attempt.
Earlier temporary-container results above do not establish a current VS Code connection.

Host file checks passed:

- `frontend/package-lock.json`: present, 28,611 bytes; Python JSON validation confirmed
  lockfile version 3 and exact direct-dependency matches with package.json.
- `backend/requirements.in`: present, 96 bytes; Flask==3.1.3.
- `backend/requirements.txt`: present, 109 bytes; seven pinned dependencies as recorded above.

Runtime and installed-dependency checks in the configured container terminal are
**blocked / not performed**, not passed. No extra dependencies were installed to
work around the missing connection. Final Phase 1 acceptance remains **incomplete**:
open this workspace in VS Code's configured Dev Container, then rerun runtime and
dependency checks in its terminal. Phase 2 remains unstarted.

## Resolved versions

Backend: Flask 3.1.3, blinker 1.9.0, click 8.5.0, itsdangerous 2.2.0,
Jinja2 3.1.6, MarkupSafe 3.0.4, Werkzeug 3.1.9. requirements.txt was generated
by pip freeze from a fresh Linux virtual environment, then installed and checked
again in the combined image. It pins versions, not wheel hashes, and targets
the verified Linux/Python environment; other platforms are not certified.

Frontend: React 19.3.0, React DOM 19.3.0, Bootstrap 5.3.8, Vite 8.3.4,
@vitejs/plugin-react 6.1.2. Transitive versions and integrity data are in npm's
generated package-lock.json. Host verification used Node 24.16.0/npm 11.13.0.

The Dockerfile records immutable digests for both official base images. No V17,
database, authentication, PDF or cloud libraries have been added.

## Commands and failures

Read-only inspection: Get-Location, Get-ChildItem -Force, Get-Content debug.log,
Get-Content on foundation files, and Get-FileHash debug.log.
Directory creation used New-Item -ItemType Directory for the approved structure;
foundation text files were written with apply_patch. No Git initialization ran.

Docker's first sandbox query failed with:
`permission denied while trying to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`.
An approved elevated invocation downloaded the images:

```powershell
docker pull python:3.12-slim-bookworm
docker pull node:24-bookworm-slim
```

The initial sandbox npm resolution failed with ENOTCACHED, cache mode
`only-if-cached`. Approved registry access succeeded. From frontend/:

```powershell
npm install --package-lock-only --save-exact react react-dom bootstrap --cache .npm-cache --no-audit --no-fund
npm install --package-lock-only --save-dev --save-exact vite @vitejs/plugin-react --cache .npm-cache --no-audit --no-fund
npm ci --cache .npm-cache --no-audit --no-fund
```

Backend resolution ran in a temporary official Python container with only backend/
mounted at /work. Its shell commands were:

```sh
python -m venv /tmp/resolve
/tmp/resolve/bin/pip install --no-cache-dir -r requirements.in
/tmp/resolve/bin/pip check
/tmp/resolve/bin/pip freeze > requirements.txt
python --version
```

Flask was then pinned in requirements.in to the observed 3.1.3 version.

```powershell
docker build --tag ayur-sage-foundation:phase1 --file .devcontainer/Dockerfile .devcontainer
```

Build succeeded. The first docker run check failed before validation because nested
PowerShell/JavaScript quoting produced `Syntax error: "(" unexpected`. The corrected
run used `docker run --rm --mount type=bind,source=<workspace>,target=/workspace,readonly
ayur-sage-foundation:phase1 sh -c <commands>` with these commands:

```sh
set -eu
python --version
node --version
npm --version
id
test ! -S /var/run/docker.sock
python -m pip install --no-cache-dir -r /workspace/backend/requirements.txt
python -m pip check
python -m flask --version
mkdir /tmp/frontend
cp /workspace/frontend/package.json /workspace/frontend/package-lock.json /tmp/frontend/
cd /tmp/frontend
npm ci --no-audit --no-fund
npm ls --depth=0
./node_modules/.bin/vite --version
```

The corrected run exited 0. Temporary containers were removed by --rm; official
images and the new development image remain. Existing containers/volumes were not
altered. No global host dependency installation was performed.

Windows PowerShell ConvertFrom-Json could not parse npm's empty root package key
in package-lock.json. Its subsequent optimistic status line was not evidence of a
pass. Python's json parser successfully validated all three JSON files and checked
the lockfile version and direct-dependency matches. Environment values and the
absence of a configured Docker socket were also checked with Python assertions.

## Remaining limits

No application tests or frontend build were run because no application exists.
No vulnerability audit, cloud deployment or clinical validation was performed.
Generated Windows node_modules and the local npm cache remain ignored inside the
workspace. VS Code may require the Dev Containers extension; installing it and
reopening the workspace are still needed to close that acceptance criterion.
No outside project files were edited by our commands; Docker manages its own image
storage as part of the authorized image pulls/build. Keep this distinction when
reviewing the external-file safeguard.
