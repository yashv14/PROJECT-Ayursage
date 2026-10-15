# V17 loading audit: Step 1 only

## Step 1.3.5 focused corrections (current; 12 October 2026)

Step 1.3 remains NOT ACCEPTED. No controlled Docker worker or full watchdog audit
was run in this step, because an external observer surviving teardown has not been
validated. The sections below retain historical evidence, not current acceptance.

Heartbeat.write() still writes heartbeat.pending and publishes using Path.replace().
Only replacement errors carrying Windows winerror 5, 32 or 33 are retry candidates;
these codes do not establish the original native handle's identity. Pending-file
write failures and other replacement errors are not retried. There are at most
three attempts with 25ms intervals, and a 200ms attempt-scheduling window capped
by the manifest's overall deadline. Scheduling limits do not bound a stuck
filesystem call or OS sleep. Deadline checks are repeated before attempts and after
publication; late global-deadline publication is rejected. Heartbeat.read() also
rejects observations after the global deadline. The existing independent recovery
and unconditional-deadline limitations are unchanged.

A single value and timestamp are retained for every attempt of a write call.
Failed replacement leaves the previous published value unchanged. Retry success
publishes that original value, not the time of the last retry. Records include
operation_phase, source/target paths, attempt, attempt_before, original before,
after, errno, winerror, exception type and retry outcome. Persistent failure,
insufficient retry budget, invalid reads or incomplete logging remain rejected;
no manifest-start substitution or direct-write fallback was introduced. If a
filesystem operation actually completes after the global deadline, its physical
publication cannot be undone, but it is not accepted as a timely heartbeat.

The focused native Windows test deliberately opens a temporary JSON file for
reading without delete sharing, observes actual replacement denial, closes that
known test handle and verifies retry success with the same timestamp. This proves
mitigation for that controlled fixture, not the cause of the historical WinError 5.
The responsible original handle remains UNDETERMINED.

observe_container_exit() replaces the invalid post-stop docker exec with bounded
Docker wait and exact-ID/label inspect. Those operations establish container-level
status only; parent/child flags remain false and recovery is required. The event
query now extends beyond FinishedAt using a recorded finite host UTC cutoff;
missing events, daemon clock differences or command timeouts remain inconclusive.
This corrected Docker path was tested with mocks, not a new live container.

classify_tracked_termination() is a pure supplied-evidence validator for focused
regressions. It checks a valid two-process precondition, observer validation and
survival declarations, target namespace/boot, exact PID/PPID/start identities and
both exit observations. It opens no PID descriptors and implements no collector.
Synthetic observer records are test fixtures, not runtime proof. These JSON fields
are not authorization or a substitute for independently validating a real collector.
The current runner does not use them to elevate container exit into descendant proof.

Read-only environment inspection found the desktop-linux named-pipe context,
WSL namespace pid:[4026532219], nsenter on PATH, and no Python executable returned
by command -v python/python3. Windows host Python does not expose os.pidfd_open.
The earlier Docker-to-WSL PID relationship remains unvalidated. No namespace entry,
privilege change, compiler/build, package install or observer provisioning was
attempted. nsenter availability alone is not a validated observer. No guardian is
provisioned; a guardian test would prove its own tracked-child waits before exit,
not this whole-container KILL boundary.

Before a future live test, a reviewed observer must acquire references to the exact
parent and child while alive, establish their daemon-host PID mapping and start
identities, remain available after worker teardown and record independent exits
within the existing deadline. Its failure, timeout, wrong namespace, PID reuse or
missing evidence must reject the run. Until those prerequisites are established,
no targeted live test or full watchdog acceptance audit is authorized by this step.
Loading remains disabled; no ML runtime setup is performed.


## Step 1.3.3 diagnostic instrumentation (current; 12 October 2026)

Step 1.3 remains NOT ACCEPTED. This section updates the heartbeat/evidence portions
of Step 1.3.1; its other rejection and completion controls remain in effect.

worker_diagnostics.py supplies structured, versioned Heartbeat records. The writer
and reader record run/scenario, PID/parent PID, executable/platform, clock domain,
write/read start/end, exact value, age, threshold, outcome and exception type.
Both are local Windows processes using GetTickCount64() through time.monotonic().
Linux process start ticks/boot and namespace IDs are identities only; no Linux
monotonic timestamp is subtracted from a Windows timestamp. Missing/invalid JSON,
read errors, future/regressing stamps and inconsistent clock/run metadata raise an
explicit HeartbeatError. monitor() records heartbeat_observation_unavailable and
requests termination and keeps the run rejected even after safety termination;
it no longer substitutes the manifest start time. Stale
valid values retain the original three-second recovery condition.

Heartbeat records are queued without waiting for disk. Each logger has a queue
of 32, at most 1024 records of at most 8192 bytes, and a 0.5-second final drain.
Overflow, serialization/write errors or a stuck daemon writer preserve incomplete
evidence. The diagnostic runner bounds its raw command-record publication wait to
0.5 seconds and marks an incomplete publication explicitly; the underlying writer
may still be stalled or finish later. No final result may be accepted with absent
or false diagnostics_complete. completion() additionally requires the supervisor's
writer-completion status. Atomic heartbeat publication, existing legacy event/kill
journals, manifest/final-result operations, OS scheduling and host stalls are not
made unconditionally bounded by this logging mechanism. A virtual environment is
not a sandbox. The existing independent recovery/deadline limitations still apply.

worker_control_probe.py's timeout mode additionally records parent/child /proc
stat, PID/PPID, start ticks, PID/mount namespaces and boot ID in scratch and stdout.
Its observe mode reads those two processes from a docker exec observer in the
worker's own namespace. Matching identity requires the same boot, start ticks,
parent relationship and observer/worker PID namespace, with non-zombie states.
The controls/failure modes and fixed Docker restrictions are preserved.

worker_diagnostic_audit.py conducts one diagnostic worker test, with a separate
host heartbeat publisher. It is not the four-scenario watchdog acceptance audit.
It creates only the existing restricted timeout probe, inspects exact ID/labels,
records initial/WSL/Docker observations, and requires a fresh matching inside
observation before KILL. Its precondition permits at most one second between the
completed fresh observation and the request. Safety KILL on failure is recorded
separately and never substitutes for that precondition. No container is deleted.
The diagnostic reader records stale decisions; this experiment schedules KILL
following its fresh identity observation rather than claiming to test the full
watchdog trigger. Raw results and one checksum-bound completion receipt are kept.
Step acceptance is always false for this diagnostic-only run.

The actual test recorded a Windows replacement PermissionError (WinError 5).
The reader overlapped that write in the same clock tick; this supports a sharing
conflict hypothesis but does not identify the native handle holder. Publication
failure, publisher exit 1 and subsequent stale values are VERIFIED in the new run.
The historical heartbeat failure's cause remains UNDETERMINED.

Inside observations validated parent PID 1 / child PID 8, start ticks 9218/9262,
namespace pid:[4026532383] and boot 8f6ec594-425a-42cf-9f9e-4aeaeb5e2cb1.
Docker reported 439/453 with relationship 416 -> 439 -> 453. WSL reported those
PIDs absent while the inside observation established the processes alive. The
namespace relationship is not established: the live namespace query's multi-file
readlink was incompatible with BusyBox. It was corrected to individual readlink
calls, without repeating the controlled worker. A later read-only supplement has
a different boot ID, so it cannot validate the earlier mapping. Same-number PID
comparison remains inconclusive, including for historical PIDs 481/494.

KILL exited 0 and Docker recorded exit 137. Post-KILL docker exec exited 1 because
the container was not running. No observer surviving namespace teardown was
provisioned: parent/child termination remains UNVERIFIED despite container exit.
Result accepted=false/recovery_required=true; no model loading is permitted.
The event query ended at State.FinishedAt and captured KILL but not a separate die
event; it must not be described as complete lifecycle-event evidence.

The next narrow correction to review is a Windows heartbeat publication/read
method that tolerates or avoids the demonstrated replacement failure while still
reporting errors and enforcing the same stale threshold. A separately reviewed
observer must establish the correct namespace and survive worker teardown before
claiming descendant termination. Neither correction is implemented here. Historical
causality, real daemon-loss recovery and unconditional hard deadlines remain open.


## Step 1.3.1 current protocol and limitations (12 October 2026)

This section supersedes the Step 1.3 completion/acceptance descriptions below.
Step 1.3 is NOT ACCEPTED. Loading remains disabled.

- The coordinator owns the watchdog process handle and starts it before the
  supervisor. Both run the base Python interpreter directly, using only standard
  library supervision code. A Windows venv launcher was observed to spawn another
  interpreter process: launcher PID 35176, child PID 22948, child parent 35176.
  Direct base launch recorded handle/self PID 35488. Evidence is retained in
  reports/step-1-3-1/identity-diagnostic.json. This demonstrates the redirector
  mechanism; the historical 2192/15700 records lack ancestry data, so their exact
  historical relationship cannot be reconstructed conclusively. No WSL namespace
  is involved in the new Windows watchdog identity. Launch/ready records retain
  executable, host PID namespace, parent PID and a per-run token; completion
  validates them against the coordinator-owned handle and its actual exit status.
- The watchdog publishes result.json exactly once, after log/state and descendant
  evidence collection. publish() flushes/fsyncs a unique pending file then creates
  a hard link under the final name, failing if it already exists. Pending files
  are retained. This is no-replacement publication by the harness, not filesystem
  immutability against another host writer, power-loss durability, or protection
  against a stalled filesystem call.
- A result file alone is preliminary evidence for audit acceptance. completion()
  requires the watchdog handle to have exited, validates identity, binds its
  result bytes with SHA-256 in a single completion.json receipt, then rereads the
  result to detect conflicts. results.json contains the final acceptance decision.
  scenario_passed() requires explicit, correctly typed acceptance, deadline,
  container/descendant termination, cleanup, finalization, identity and completion
  flags; contradictions/missing values fail. Expected worker exit 137 can pass;
  an unexpected watchdog exit cannot. Audit exit 0 requires all four scenarios.
- The monotonic budget remains 35 seconds from before manifest publication and
  either process launch; termination threshold remains 25 seconds. Acceptance is
  now timed through watchdog exit, supervisor exit, completion receipt publication
  and result reread. The later aggregate summary write is excluded. An accepted
  sample is not an unconditional bound. Docker/WSL calls have finite subprocess
  timeouts, but sequential calls, OS scheduling, filesystem calls, host process
  waits and fallback recovery can overrun. Atomic publication does not solve hangs.
- Descendant-before.json records raw docker top rows, container ID, WSL /proc stat
  observations, boot ID, PIDs, exit status, stderr and monotonic observation times.
  Termination attempts record the inspected container ID and KILL operation.
  Descendant-final.json retains both observations and any inconclusive result.
  Acceptance requires at least parent and child to be present before termination,
  matching Docker PID/parent relationships, and absent afterward in the same boot.
  Presence afterward (including possible PID reuse), unresponsive WSL, a different
  boot or missing evidence fails. Absence proves only disappearance of the observed
  PIDs at that time, not all possible unobserved descendants. The fixed controls
  probe has no child launch and records an explicit exemption. Containers remain
  restricted throughout; no host Python process substitutes for the worker.
- The real run exposed an unusable observation: Docker PIDs 481/494 were already
  ABSENT in the WSL /proc view before termination. Their disappearance cannot be
  established. This could reflect a namespace/lifecycle mismatch; the cause is
  unresolved. The run correctly reports termination_unconfirmed/recovery_required
  despite a stopped container. Historical absence-only checks are insufficient.
- If the watchdog exits unexpectedly or has not exited by start +40 seconds, the
  surviving coordinator stops the creator before best-effort, exact-label/ID
  recovery. It stops its own stalled watchdog handle when needed. A failed run
  stays rejected even if fallback stops the container. Recovery requires descendant
  evidence too; a Created worker remains unconfirmed. Coordinator crash/stall,
  simultaneous failures, a hung host, or an unavailable daemon have no independent
  service/VM fallback. Fault-injection tests verify fail-closed reporting and
  coordinator branches, not real daemon-loss recovery or guaranteed termination.

The next prerequisite is a reviewed, testable observation path for the actual
Docker worker PID namespace, followed by all four scenarios passing this protocol.
Do not bypass the before-observation requirement or broaden worker privileges to
obtain a pass. Independent failure recovery and strict deadline guarantees remain
unverified. No system configuration change or loading approval is implied.


The scaffold verifies approved file identities. It has no deserializer, inference
callable, training-source import, package installer or Flask integration.
Checksum success means file identity only. Loading remains disabled pending review.

## Current verification procedure

From the workspace root:

```powershell
ml/.venv/Scripts/python.exe -B -m ml.inference.audit
ml/.venv/Scripts/python.exe -B -m unittest discover -s tests/ml -p 'test_*.py' -v
```

Exit 0 means both checksums matched, with model_loaded and inference_executed false.
Missing/unreadable files or mismatches exit 1. `--load` always refuses loading:
it exits 1 if verification fails, or 2 after matching checksums. There is no enable
flag or environment override. `--workspace` selects a root, not alternative hashes.
The training dataset is not read by this scaffold.

## Step 1.1 retained-byte boundary

`read_verified_file(path, artifact)` reads opaque bytes once and returns a frozen
`VerifiedArtifact` only if its constructor verifies those exact bytes against the
expected digest. The buffer is immutable `bytes`, excluded from the object repr.
`verify_workspace_buffers()` requires both fixed approved identities and returns
their retained objects. The scaffold derives its JSON metadata from these objects;
it does not put binary bytes into logs or JSON. No deserializer was added.

A future separately authorized loader must accept a verified object and consume
only its `.buffer`, e.g. by wrapping that buffer in an in-memory stream. It must not
accept a filesystem path or use metadata as a loading authorization token. The
relative path in the artifact specification identifies provenance, not something
to reopen. Source extraction must likewise parse the retained source bytes.
Verification is not permission to execute serialized code; dependency/isolation
approval is still separate. Frozen dataclasses do not defend against hostile code
already running in the same interpreter.

The regression test replaces a temporary file immediately after its single read,
checks that the retained original bytes remain verified, prevents path reopening
during buffer consumption, and confirms a fresh read rejects the replacement.
Other tests reject mutable/unverified buffers. Two unpatched tests assert literal
approved model/source hashes independently of the production manifest.

## Dependency plan: not an installation authorization

Keep root `.venv`, backend/requirements.in and backend/requirements.txt unchanged.
Use `ml/.venv/` with Python 3.12.7 and system-site-packages disabled. Step 1 can
create it with `python -m venv --without-pip ml/.venv`; no pip or ML packages are
needed for checksums and unittest. Do not overwrite an existing audit environment.

| Component | Recorded training metadata | Historical experimental audit candidate |
| --- | --- | --- |
| Python | 3.12.7, Windows | 3.12.7 |
| scikit-learn | 1.9.0 | 1.9.0 |
| NumPy | Version unavailable | 2.4.6 |
| pandas | Version unavailable | 3.0.3 |
| SciPy | Version unavailable | 1.18.0 |
| joblib | Version unavailable | 1.5.3 |
| XGBoost | Available; selected XGB, version unavailable | 3.3.0 |

Evidence: older Downloads/AYUR_mega/AYUR_mega/results/metadata.json and
Videos/AYURSAGE/docs/phase5-evidence.md. Metadata provenance is not independently
bound to the model. Historical candidates are not original training pins or
production recommendations. The older audit inherited system packages.

Before installation, review exact XGBoost, NumPy, pandas, SciPy and joblib versions
from the original environment where obtainable, plus a resolved transitive lock
and wheel hashes for a clean audit environment. If unavailable, explicitly approve
an experimental candidate set and label results with that exact runtime; do not
claim original-runtime reproduction. No dependency lock is fabricated in Step 1.
Training/plotting packages, Flask, databases and cloud packages are outside this
inference-only plan. Do not import the training module to satisfy dependencies.

## Restricted future execution procedure: requires separate approval

This is a procedure to prepare, not a command to load now. A venv is dependency
isolation, not a security boundary for executable serialized objects.

1. Review this scaffold, dependency plan, trusted artifact/source hashes and the
   proposed inference-only extraction. Do not run older extraction/audit scripts
   unchanged: extraction writes files; the audit loads the model and executes
   selected source. The older derivative changes global random-state handling.
2. Provision a disposable restricted worker with the approved locked runtime.
   Match Windows/Python 3.12.7 first if reproducing recorded metadata. A later Linux
   container test is a separate portability check. Keep the application venv separate.
3. Before execution, enforce network denial at the OS/container boundary and test
   it. For a reviewed Linux audit image, Docker `--network none` is one option;
   provide no Docker socket. Environment variables or absence of HTTP code do not
   constitute network isolation. If isolation cannot be enforced, do not load.
4. Give the worker only read-only production-model access and reviewed audit code.
   Do not mount the entire workspace, datasets, patient files, credential folders,
   root venv or secret files. Supply an allowlisted environment without credentials,
   tokens or cloud identity. Use a non-admin worker and a disposable writable scratch
   directory; no published ports. Verify that model writes are denied before loading.
5. Use a parent supervisor outside the worker with a 60-second hard deadline for
   the first load/structure attempt. This is an operational audit limit, not measured
   model performance. On expiry, terminate the entire worker/process tree, mark the
   attempt failed and require review before changing the limit. Bound memory/CPU.
6. A future loader must read model bytes once, hash those exact bytes against the
   approved digest, then deserialize the same verified buffer. Do not use Step 1's
   metadata report as an authorization token or reopen a previously verified path.
   Reject missing artifacts, changed hashes and compatibility warnings; no fallback
   models, conversion, refitting or repair.
7. Validate the trusted bundle against the recorded XGB selection, exact 12-feature
   and four-target order, fitted transformer/encoders/classifiers and source engine
   mappings. Post-load validation is not protection against malicious pickle code.
8. Report load and structure results only. Inference requires owner-approved
   synthetic inputs and complete expected outputs bound to model/source hashes and
   runtime evidence. Historical demo variants are unapproved candidates, not fixtures.
9. Keep outputs unapproved with PENDING_DOCTOR_REVIEW. No treatment approval,
   prescriptions, patient release, reports or prediction endpoint are implemented.
   Future doctor authorization/approval must be enforced separately by Flask.

## Concrete Windows-host worker design (not provisioned)

**Step 1.2 update:** Docker is now running and harmless control probes have run.
The inspection below describes Step 1.1's historical state. See verification.md
for current observations. The new `infra/docker/worker_control_audit.py` is a
harmless polling supervisor, not the independent watchdog specified below. Its
5-second timeout probe ran about 6.07 seconds inside the container; command latency
means it does not establish a hard deadline. Do not use it to load models.
Network/read-only/scratch/log checks passed with test inputs only. Supervisor-crash
and daemon-loss recovery remain untested. All created test containers were retained.

Read-only inspection on 12 October 2026 found Docker Desktop CLI 29.8.1 for
Windows/amd64, context `desktop-linux`. Its server is unavailable: the
`dockerDesktopLinuxEngine` named pipe was not found. `hns` and `vmcompute` services
are running, which does not prove a usable Docker worker. `WindowsSandbox.exe`
is absent. Registry reports CoreSingleLanguage, build 26300, DisplayVersion 26H2,
with a legacy ProductName string of Windows 10 Home Single Language; no stronger
OS-edition claim is inferred from that inconsistent label. No feature was enabled.

The proposed execution target is a disposable Linux container supervised from
Windows PowerShell through Docker Desktop. This is an explicitly experimental
Linux portability audit, not reproduction of the metadata's Windows training
environment. If exact Windows reproduction is required, a separately provisioned
disposable Windows VM with equivalent tested controls is a prerequisite; do not
substitute the current venv for it.

After separate approval and runtime preparation, use a reviewed image pinned by
digest with audit code/runtime baked in and no credentials in layers or ENV. Create
the worker stopped, with a unique name and captured container ID. Do not pull an
image during the audit (`--pull never`). The planned Docker create arguments are:

```text
--network none --read-only --user 1000:1000 --cap-drop ALL
--security-opt no-new-privileges=true --pids-limit 64 --memory 2g --cpus 1
--restart no --log-driver local --log-opt max-size=10m --log-opt max-file=1
--log-opt compress=false
--tmpfs /scratch:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700
--workdir /scratch
--mount type=bind,source=<absolute model file>,target=/inputs/model.pkl,readonly
--mount type=bind,source=<absolute source file>,target=/inputs/source.py,readonly
--env HOME=/scratch --env TMPDIR=/scratch --env PYTHONDONTWRITEBYTECODE=1
--env OMP_NUM_THREADS=1 --env OPENBLAS_NUM_THREADS=1
```

Use default private PID/IPC namespaces and default seccomp. No host networking,
privileged mode, devices, Docker socket, host workspace/profile, dataset mount,
env-file, inherited secret values, named persistent volumes or published ports.
`--network none` leaves container-local loopback; the requirement is denial of
external/host network access. Do not claim that loopback is disabled.
If zero socket use is required, a separately reviewed syscall policy is needed.
The only writable worker location is ephemeral `/scratch`; Docker-managed logs
are collected by the supervisor, not written through a worker host-directory mount.

### Supervision and evidence capture

**Step 1.3 implementation:** `infra/docker/worker_watchdog.py` runs a separate host
watchdog process before container creation. The container remains the only worker;
host Python processes perform supervision only. The older polling audit is retained
as historical/simple control coverage, not the current recovery mechanism.

The real harmless audit uses a 35-second complete-operation budget. Start is the
monotonic timestamp immediately before manifest publication and supervisor launch;
container creation/startup are included. Termination begins at 25 seconds, leaving
10 seconds for shutdown and evidence capture. A heartbeat stale for 3 seconds after
startup independently triggers recovery. Pending startup is distinguished from a
missing daemon so normal creation cannot trigger premature termination.
The end measurement is taken after stopped-state verification, separate log/state
writes and first result.json publication. The final timing annotation and subsequent
separate stale-run recovery inspection are not included. No containers or fixtures
are deleted: cleanup_completed means evidence finalized and worker quiescent, not
resource removal. Container scratch ends with namespace teardown.

The watchdog reports deadline_met/deadline_exceeded independently of termination
confirmation and cleanup. Each Docker monitoring command has a 2-second timeout;
creation has a 20-second timeout. Recovery observation is bounded to deadline +5
seconds; this extra diagnostic window cannot turn an overrun into acceptance.
Synchronous commands and Windows/WSL scheduling can overshoot even that window.
Recorded samples within budget are not an unconditional strict-deadline guarantee.

Run manifests, atomic report publications and an append-only event journal survive
supervisor failure. Created workers carry exact audit ownership labels; kill and
recovery verify those labels before acting. Recovery accepts only a recorded worker,
never starts it and never deletes resources. Old unlabelled workers are not adopted.
Completed labelled runs were re-inspected successfully. The first interrupted
Created run remains recovery_required: it is not running, but its lifecycle evidence
is incomplete. No uncertainty is promoted to a successful recovery.

Real supervisor exit 23 and a stalled supervisor were tested. Daemon loss was tested
only with deterministic injected control-channel failures, which preserve uncertain
termination and require recovery. No Docker Desktop/WSL shutdown occurred. A tested
independent VM-level termination path is still missing if the daemon is unreachable.
Loading remains disabled; this watchdog accepts harmless probe workers only.

The future PowerShell supervisor must start an independent watchdog **before**
starting the stopped container. Launch helpers with `Start-Process -WindowStyle
Hidden`. The watchdog records a monotonic 60-second deadline before `docker start`,
so startup and loading are included. It polls the named container's state through
Docker with short per-command timeouts and never passes a wildcard or unrelated
container ID to cleanup. Do not depend on a long blocking `docker wait` call.

On normal completion, collect `docker inspect` State.ExitCode, OOMKilled and Error,
and `docker logs --timestamps` stdout/stderr separately into an ignored dedicated
host `reports/` audit-run directory. Record image digest, safe runtime/version
metadata, artifact digests and elapsed time. Limit logs and exclude model buffers,
patient inputs, credentials and clinical outputs. Do not use `--rm` until exit
status and logs have been captured.

On deadline or supervisor failure, the watchdog sends `docker kill --signal KILL`
to the exact container ID. With a private PID namespace, container teardown is the
mechanism for terminating all worker descendants; terminating only docker.exe or
using Stop-Process on the CLI is insufficient. Confirm State.Running is false,
capture available state/logs and retain that worker. Removal requires explicit
approval and is not part of the implemented audit or its cleanup semantics.
Report TIMED_OUT separately from the container exit code. A monitor/probe failure
is not success. If the Docker daemon becomes unreachable, container termination
cannot be guaranteed through the CLI: a tested dedicated worker-VM teardown path
is required for that failure case. Without it, this control remains incomplete.

### Required harmless provisioning tests before any pickle loading

- Confirm image/environment/mount inventory contains only approved inputs and no
  inherited credentials; networking and mount policy must remain fixed for the
  whole worker lifetime. Test denied outbound TCP and DNS against a controlled
  test target without sending sensitive content.
- Using disposable fixture files, confirm model/source writes fail and scratch
  writes succeed. Do not attempt writes to the real frozen files as a probe.
- Run a harmless worker that spawns a long-lived child. Prove the watchdog deadline
  terminates both parent and child; test supervisor interruption and daemon failure
  recovery without touching unrelated containers or services.
- Run harmless success/failure workers and verify captured exit codes, distinct
  stdout/stderr, bounded logs and timeout status before enabling a loading attempt.

At Step 1.1 none of these controls had been provisioned or tested. Step 1.2 tested
the basic controls using the existing official Python image, without ML packages.
Remaining prerequisites are an approved pinned loading runtime, an independent
watchdog with measured deadline enforcement, tested supervisor/VM-failure recovery,
and separate loading approval. Loading remains disabled until these requirements
are met. The harmless probe image's Python 3.12.15 does not reproduce Python 3.12.7.
Docker option semantics were reviewed against the official
[run reference](https://docs.docker.com/reference/cli/docker/container/run/),
[kill reference](https://docs.docker.com/reference/cli/docker/container/kill/) and
[logs reference](https://docs.docker.com/reference/cli/docker/container/logs/).

## Unresolved evidence

The copied dataset hash is
`92e9ef2c1d445cc125720c9c6c880747673b5c48c6ad37e17007573edab8130c`.
The same-named Downloads-root file has hash
`ac1592bc080e3aafddbaa0db24df50ab9f0278080e2491b2a4af73c1dde7e720`.
They differ at 9,950 row positions and are not identical row multisets. No reviewed
training-time checksum links either to the model. Filename/schema/size matching
does not resolve provenance. Neither file may be selected or replaced on that basis.
Dataset provenance, complete original versions, runtime compatibility, successful
inference and authorized reference fixtures remain unresolved.
