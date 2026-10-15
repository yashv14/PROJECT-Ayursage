"""Independent, harmless-only watchdog. Never deletes resources or loads ML files."""

import json
import hashlib
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from worker_control_audit import ROOT, IMAGE, create_worker
from worker_diagnostics import EvidenceLog, Heartbeat, HeartbeatError


def publish(path, value):
    """Publish once, atomically, without replacing an existing final record."""
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.pending')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)  # Fails if destination exists; pending evidence retained.


def scenario_passed(report):
    """No default success: operation, finalization and completion are separate gates."""
    yes = ('accepted', 'deadline_met', 'termination_confirmed', 'container_exit_confirmed',
           'descendants_confirmed', 'cleanup_completed', 'evidence_finalized',
           'watchdog_completed', 'identity_verified', 'completion_deadline_met', 'diagnostics_complete')
    no = ('deadline_exceeded', 'termination_unconfirmed', 'recovery_required')
    if not isinstance(report, dict) or any(report.get(k) is not True for k in yes):
        return False
    if any(report.get(k) is not False for k in no):
        return False
    if report.get('terminal_state') != 'FINAL' or type(report.get('watchdog_exit')) is not int or report['watchdog_exit'] != 0:
        return False
    for key in ('elapsed_seconds', 'completion_elapsed_seconds', 'budget_seconds'):
        value = report.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return False
    if not 0 <= report['elapsed_seconds'] <= report['completion_elapsed_seconds'] <= report['budget_seconds']:
        return False
    if type(report.get('exit_code')) is not int or type(report.get('supervisor_exit')) is not int:
        return False
    scenario = report.get('scenario')
    return ((scenario == 'complete' and report['exit_code'] == 0 and report['supervisor_exit'] == 0 and report.get('reason') == 'worker_completed')
        or (scenario == 'timeout' and report['exit_code'] == 137 and report['supervisor_exit'] == 0 and report.get('reason') == 'deadline_reserve')
        or (scenario == 'crash' and report['exit_code'] == 137 and report['supervisor_exit'] == 23 and report.get('reason') == 'supervisor_unresponsive')
        or (scenario == 'unresponsive' and report['exit_code'] == 137 and report['supervisor_exit'] in (0, 1) and report.get('reason') == 'supervisor_unresponsive'))


def wsl_observation(pids):
    """Read-only observation in the Docker Desktop Linux PID namespace.

    NOTE: This path is retained for the recover() fallback only. It is unreliable as a
    primary observer because the docker-desktop WSL distro shell runs in a different PID
    namespace than the container processes; container PIDs from 'docker top' are absent
    in /proc as seen from that shell. Use docker_top_observation() for the primary path.
    """
    if not pids or any(type(pid) is not int or pid <= 0 for pid in pids):
        raise ValueError('INVALID_PROCESS_INVENTORY')
    script = 'cat /proc/sys/kernel/random/boot_id; '
    for pid in pids:
        script += f'if test -d /proc/{pid}; then cat /proc/{pid}/stat; else echo ABSENT:{pid}; fi; '
    started = time.monotonic()
    result = subprocess.run(['wsl', '-d', 'docker-desktop', '--exec', 'sh', '-c', script],
        capture_output=True, text=True, timeout=2)
    return {'namespace':'docker-desktop:/proc', 'monotonic':started,
        'finished':time.monotonic(), 'pids':pids, 'exit_code':result.returncode,
        'stdout':result.stdout, 'stderr':result.stderr}


def docker_top_observation(container_id, name, pids):
    """Capture pre-termination process identity via 'docker top'.

    'docker top' runs in the Docker daemon context and reliably sees the container
    process tree regardless of WSL PID namespace boundaries. The returned record serves
    as the pre-termination identity evidence for descendants_confirmed_via_docker().

    Raises ValueError if the observed PIDs do not match or the relationship is absent.
    Raises RuntimeError/subprocess.TimeoutExpired on Docker daemon failures.
    """
    if not pids or len(pids) < 2 or any(type(p) is not int or p <= 0 for p in pids):
        raise ValueError('INVALID_PROCESS_INVENTORY')
    started = time.monotonic()
    result = subprocess.run(['docker', 'top', container_id, '-eo', 'pid,ppid,args'],
        capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError('DOCKER_TOP_FAILED_PRECONDITION')
    top_text = result.stdout
    rows = [row.split(None, 2) for row in top_text.splitlines()[1:]]
    top_pids = [int(row[0]) for row in rows if row]
    # All expected PIDs must be present in docker top output.
    if not all(p in top_pids for p in pids):
        raise ValueError('EXPECTED_PIDS_NOT_IN_DOCKER_TOP')
    parents = {int(row[0]): int(row[1]) for row in rows if row}
    # At least one parent-child relationship must exist among the tracked PIDs.
    if not any(parents.get(p) in pids for p in pids):
        raise ValueError('CHILD_RELATIONSHIP_NOT_CONFIRMED')
    return {'mechanism': 'docker_top', 'container_id': container_id,
        'container_name': name, 'pids': list(pids),
        'docker_top': top_text, 'parents': parents,
        'monotonic': started, 'finished': time.monotonic()}


def descendants_disappeared(before, after):
    """Only absence of previously observed PIDs in the same boot is evidence.

    Accepts two evidence formats:

    1. WSL /proc format (legacy, used by recover()): both 'before' and 'after' have
       'namespace', 'pids', 'stdout', 'exit_code', 'docker_top', 'finished' /
       'monotonic' keys. 'before' stdout must contain real /proc/<pid>/stat lines;
       'after' stdout must show ABSENT:<pid> for all tracked PIDs.

    2. Docker-top format (primary, used by verify_descendants()): 'before' has
       'mechanism'=='docker_top', 'container_id', 'pids', 'docker_top', 'parents';
       'after' has 'mechanism'=='docker_top_absent', 'container_id', 'top_failed'==True,
       'container_exited'==True, 'monotonic' >= before['finished'].
    """
    try:
        if before.get('mechanism') == 'docker_top':
            # Docker-top format: validate identity then check post-termination evidence.
            pids = before['pids']
            parents = before['parents']
            after_mech = after.get('mechanism')
            return (after_mech == 'docker_top_absent'
                and before['container_id'] == after['container_id']
                and after.get('top_failed') is True
                and after.get('container_exited') is True
                and len(pids) >= 2 and len(set(pids)) == len(pids)
                and pids == after.get('pids')
                and after.get('monotonic', 0) >= before['finished']
                and set(parents) >= set(pids)
                and any(parents.get(p) in pids for p in pids))
        # WSL /proc format (legacy path).
        pids = before['pids']
        first, last = before['stdout'].splitlines(), after['stdout'].splitlines()
        rows = [row.split(None, 2) for row in before['docker_top'].splitlines()[1:]]
        parents = {int(row[0]):int(row[1]) for row in rows}
        return (before['namespace'] == after['namespace'] == 'docker-desktop:/proc'
            and before['exit_code'] == after['exit_code'] == 0
            and len(pids) >= 2 and len(set(pids)) == len(pids) and pids == after['pids']
            and before['finished'] <= after['monotonic']
            and len(first) == len(last) == len(pids) + 1 and bool(first[0]) and first[0] == last[0]
            and all(first[i+1].startswith(str(pid) + ' (') for i,pid in enumerate(pids))
            and set(parents) == set(pids) and any(ppid in pids for ppid in parents.values())
            and all(int(first[i+1].rsplit(')',1)[1].split()[1]) == parents[pid] for i,pid in enumerate(pids))
            and last[1:] == ['ABSENT:' + str(pid) for pid in pids])
    except (KeyError, TypeError, IndexError, ValueError):
        return False


def verify_descendants(directory, manifest):
    if manifest['scenario'] == 'complete':
        # The fixed controls probe does not spawn subprocesses.
        publish(directory/'descendant-final.json', {'required':False, 'basis':'fixed controls probe has no child launch'})
        return True
    try:
        before = json.loads((directory/'descendant-before.json').read_text())
        cid = before.get('container_id', '')
        if not cid:
            raise ValueError('MISSING_CONTAINER_ID')
        # Post-termination: 'docker top' on an exited container returns non-zero.
        # This is the Docker-guaranteed evidence that all container processes are gone:
        # SIGKILL to container init causes the kernel to SIGKILL all remaining processes
        # in the container PID namespace before the namespace is torn down.
        top_result = subprocess.run(
            ['docker', 'top', cid, '-eo', 'pid,ppid,args'],
            capture_output=True, text=True, timeout=5)
        # Also inspect the container state for corroboration.
        inspect_result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Running}} {{.State.Status}}', cid],
            capture_output=True, text=True, timeout=5)
        inspect_out = inspect_result.stdout.strip().split()
        container_exited = (inspect_result.returncode == 0
            and len(inspect_out) == 2
            and inspect_out[0] == 'false'
            and inspect_out[1] == 'exited')
        after = {'mechanism': 'docker_top_absent',
            'container_id': cid,
            'pids': before.get('pids', []),
            'top_failed': top_result.returncode != 0,
            'top_stderr': top_result.stderr[:256] if top_result.stderr else '',
            'container_exited': container_exited,
            'monotonic': time.monotonic()}
        confirmed = descendants_disappeared(before, after)
        evidence = {'required': True, 'confirmed': confirmed, 'before': before, 'after': after}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        confirmed = False
        evidence = {'required': True, 'confirmed': False, 'inconclusive': type(error).__name__}
    publish(directory/'descendant-final.json', evidence)
    return confirmed


def save(path, value):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def outcome(start, deadline, finished, confirmed, cleanup):
    """Classification has no Docker dependency; no tolerance masks overruns."""
    return {'elapsed_seconds': round(finished - start, 3),
        'deadline_met': finished <= deadline,
        'deadline_exceeded': finished > deadline,
        'termination_confirmed': confirmed,
        'termination_unconfirmed': not confirmed,
        'cleanup_completed': cleanup,
        'recovery_required': not confirmed or not cleanup,
        'accepted': finished <= deadline and confirmed and cleanup}


class DockerWorker:
    def __init__(self, name, directory=None):
        if not name.startswith('ayursage-controls-watch-'):
            raise ValueError('Not an audit worker')
        self.name = name
        self.directory = directory

    def ready(self):
        return self.directory is None or (self.directory / 'started.json').exists()

    def command(self, *args):
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=2)
        if result.returncode:
            raise RuntimeError('DOCKER_OPERATION_UNAVAILABLE:' + args[0])
        return result

    def state(self):
        config = json.loads(self.command('inspect', self.name).stdout)[0]
        labels = config['Config'].get('Labels') or {}
        if labels.get('ayursage.harmless-audit') != 'true' or labels.get('ayursage.audit-name') != self.name:
            raise RuntimeError('WORKER_OWNERSHIP_MISMATCH')
        if self.directory is not None and (self.directory/'created.json').exists():
            if config['Id'] != json.loads((self.directory/'created.json').read_text())['id']:
                raise RuntimeError('WORKER_ID_MISMATCH')
        self.cid = config.get('Id', self.name)
        return config['State']

    def kill(self):
        self.state()  # Never operate on an unlabelled or unrelated resource.
        if self.directory is not None:
            with (self.directory/'termination-attempts.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps({'id':self.cid,'operation':'docker kill --signal KILL',
                    'monotonic':time.monotonic()}) + '\n')
        self.command('kill', '--signal', 'KILL', self.cid)

    def capture(self, directory):
        state = self.state()
        logs = self.command('logs', '--timestamps', self.name)
        (directory / 'worker-stdout.log').write_text(logs.stdout, encoding='utf-8')
        (directory / 'worker-stderr.log').write_text(logs.stderr, encoding='utf-8')
        save(directory / 'worker-state.json', state)
        return state


def monitor(worker, start, deadline, terminate_at, heartbeat, capture,
            *, clock=time.monotonic, sleep=time.sleep, persist=lambda event: None):
    """Injectable monitor. Errors retain explicit uncertainty instead of success."""
    reason = 'worker_completed'
    confirmed = cleanup = False
    heartbeat_failure = False
    exit_code = None
    recovery_limit = deadline + 5
    while clock() < recovery_limit:
        try:
            if hasattr(worker, 'ready') and not worker.ready():
                if clock() < terminate_at:
                    sleep(0.1)
                    continue
                reason = 'startup_deadline_exceeded'
                worker.kill()
            state = worker.state()
            if not state['Running'] and state['Status'] == 'exited':
                if reason == 'worker_control_unavailable':
                    reason = 'control_channel_recovered_worker_stopped'
                confirmed = True
                exit_code = state['ExitCode']
                break
            now = clock()
            try:
                stamp = heartbeat()
            except HeartbeatError:
                heartbeat_failure = True
                reason = 'heartbeat_observation_unavailable'
                persist({'event':reason, 'elapsed':clock()-start})
                worker.kill()
                sleep(0.1)
                continue
            now = clock()
            if now >= terminate_at or now - stamp >= 3:
                reason = 'deadline_reserve' if now >= terminate_at else 'supervisor_unresponsive'
                persist({'event': reason, 'elapsed': now - start})
                worker.kill()
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            reason = 'worker_control_unavailable'
            persist({'event': reason, 'error_type': type(error).__name__, 'elapsed': clock() - start})
            # A failed control channel cannot establish termination.
            try:
                worker.kill()
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                persist({'event':'termination_attempt_unconfirmed','elapsed':clock()-start})
        sleep(0.1)
    if confirmed:
        try:
            capture()
            cleanup = True  # Evidence finalized; containers/files retained intentionally.
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            reason = 'evidence_capture_failed'
    report = outcome(start, deadline, clock(), confirmed, cleanup)
    if heartbeat_failure:
        report.update(accepted=False, recovery_required=True)
    report['heartbeat_observation_failed'] = heartbeat_failure
    report.update(reason=reason, exit_code=exit_code)
    persist({'event': 'finished', **report})
    return report


def watch(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    worker = DockerWorker(manifest['name'], directory)
    events = directory / 'watchdog-events.jsonl'

    def persist(event):
        with events.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event) + '\n')

    diagnostic = EvidenceLog(directory/'heartbeat-reader.jsonl')
    heartbeat = Heartbeat(directory/'heartbeat.json', manifest, diagnostic)

    publish(directory / 'watchdog-ready.json', {'pid':os.getpid(), 'ppid':os.getppid(),
        'namespace':'windows-host' if os.name == 'nt' else 'host', 'token':manifest['token'],
        'executable':sys.executable})
    report = monitor(worker, manifest['start'], manifest['deadline'], manifest['terminate_at'],
        heartbeat.read, lambda: worker.capture(directory), persist=persist)
    descendants = verify_descendants(directory, manifest)
    report['container_exit_confirmed'] = report['termination_confirmed']
    report['termination_confirmed'] = report['termination_confirmed'] and descendants
    report.update(outcome(manifest['start'], manifest['deadline'], time.monotonic(),
        report['termination_confirmed'], report['cleanup_completed']))
    if report['heartbeat_observation_failed']:
        report.update(accepted=False, recovery_required=True)
    report.update(descendants_confirmed=descendants, terminal_state='FINAL',
        evidence_finalized=report['cleanup_completed'], token=manifest['token'],
        budget_seconds=manifest['deadline']-manifest['start'])
    diagnostics_complete = diagnostic.finish()
    report['diagnostics_complete'] = diagnostics_complete
    if not diagnostics_complete:
        report.update(accepted=False, evidence_finalized=False, cleanup_completed=False, recovery_required=True)
    publish(directory / 'result.json', report)
    return 0 if report['accepted'] else 1


def supervise(directory, scenario):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    save(directory / 'supervisor.json', {'pid':os.getpid(), 'ppid':os.getppid()})
    diagnostic = EvidenceLog(directory/'heartbeat-writer.jsonl')
    heartbeat = Heartbeat(directory/'heartbeat.json', manifest, diagnostic)
    heartbeat.write()
    try:
        mode = 'controls' if scenario == 'complete' else 'timeout'
        cid = create_worker(mode, manifest['name'], directory / 'fixture.txt', command_timeout=20)
        save(directory / 'created.json', {'id':cid})
        heartbeat.write()
        worker = DockerWorker(manifest['name'], directory)
        if time.monotonic() >= manifest['terminate_at']:
            raise RuntimeError('STARTUP_BUDGET_EXCEEDED')
        worker.command('start', manifest['name'])
        heartbeat.write()
        save(directory / 'started.json', {'monotonic':time.monotonic()})
        # Record both processes before intentionally losing the supervisor.
        if scenario != 'complete':
            for _ in range(15):
                heartbeat.write()
                top = worker.command('top', manifest['name'], '-eo', 'pid,ppid,args').stdout
                (directory / 'worker-processes.txt').write_text(top, encoding='utf-8')
                if len(top.splitlines()) >= 3:
                    break
                time.sleep(0.1)
            if len(top.splitlines()) < 3:
                raise RuntimeError('CHILD_NOT_OBSERVED')
            rows = [row.split(None, 2) for row in top.splitlines()[1:]]
            pids = [int(row[0]) for row in rows]
            if not any(int(row[1]) in pids for row in rows):
                raise RuntimeError('CHILD_RELATIONSHIP_NOT_OBSERVED')
            before = docker_top_observation(cid, manifest['name'], pids)
            publish(directory/'descendant-before.json', before)
            heartbeat.write()
        if scenario == 'crash':
            os._exit(23)  # Real supervisor exit; independent watchdog must survive.
        if scenario == 'unresponsive':
            time.sleep(25)  # No heartbeat, still a real restricted container worker.
        while not (directory / 'result.json').exists():
            heartbeat.write()
            if time.monotonic() > manifest['deadline'] + 8:
                raise RuntimeError('WATCHDOG_RESULT_MISSING')
            time.sleep(0.1)
        return 0
    except Exception as error:
        save(directory / 'supervisor-error.json', {'type':type(error).__name__, 'message':str(error)})
        return 1
    finally:
        save(directory/'heartbeat-writer-status.json', {'complete':diagnostic.finish()})


def recover(directory):
    """Inspect exact recorded labelled worker; never restart or delete anything."""
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    worker = DockerWorker(manifest['name'], directory)
    try:
        state = worker.state()
        if state['Running']:
            worker.kill()
            state = worker.state()
        confirmed = not state['Running'] and state['Status'] == 'exited'
        if confirmed:
            worker.capture(directory)
        descendants = manifest.get('scenario') == 'complete'
        if confirmed and not descendants:
            before = json.loads((directory/'descendant-before.json').read_text())
            after = wsl_observation(before['pids'])
            descendants = descendants_disappeared(before, after)
            save(directory/'recovery-descendants.json', {'before':before,'after':after,'confirmed':descendants})
        confirmed = confirmed and descendants
        report = {'termination_confirmed':confirmed,'recovery_required':not confirmed,
            'restarted':False,'deleted':False}
    except (RuntimeError,OSError,ValueError,KeyError,subprocess.TimeoutExpired):
        report = {'termination_confirmed':False,'recovery_required':True,'restarted':False,'deleted':False}
    save(directory / 'recovery.json', report)
    return report


def completion(directory, manifest, watchdog, supervisor_exit, *, clock=time.monotonic):
    """Called only with coordinator-owned process handle; result alone is insufficient."""
    code = watchdog.poll()
    if code is None:
        raise RuntimeError('WATCHDOG_NOT_COMPLETED')
    raw = (directory/'result.json').read_bytes()
    report = json.loads(raw)
    ready = json.loads((directory/'watchdog-ready.json').read_text())
    if not isinstance(report, dict) or not isinstance(ready, dict):
        raise ValueError('MALFORMED_FINAL_RECORD')
    if report.get('budget_seconds') != manifest['deadline'] - manifest['start']:
        raise ValueError('CONFLICTING_DEADLINE_POLICY')
    identity = (ready.get('pid') == watchdog.pid and ready.get('ppid') == os.getpid()
        and ready.get('token') == manifest['token'] and report.get('token') == manifest['token']
        and ready.get('namespace') == ('windows-host' if os.name == 'nt' else 'host'))
    if 'diagnostics_complete' in report:
        try:
            writer_complete = json.loads((directory/'heartbeat-writer-status.json').read_text())['complete'] is True
        except (OSError, ValueError, KeyError):
            writer_complete = False
        report['diagnostics_complete'] = report['diagnostics_complete'] is True and writer_complete
        if not report['diagnostics_complete']:
            report.update(accepted=False, evidence_finalized=False, recovery_required=True)
    report.update(watchdog_completed=True, watchdog_exit=code, identity_verified=identity,
        scenario=manifest['scenario'], supervisor_exit=supervisor_exit)
    receipt = {'watchdog_pid':watchdog.pid, 'watchdog_exit':code, 'identity_verified':identity,
        'result_sha256':hashlib.sha256(raw).hexdigest(), 'monotonic':clock(), 'ready':ready}
    publish(directory/'completion.json', receipt)
    # Include final publication, process exit, receipt publication and reread in the budget.
    unchanged = (directory/'result.json').read_bytes() == raw
    finished = clock()
    report.update(completion_elapsed_seconds=finished-manifest['start'],
        completion_deadline_met=finished <= manifest['deadline'])
    if not unchanged:
        report.update(accepted=False, recovery_required=True, evidence_finalized=False)
    report['scenario_passed'] = scenario_passed(report)
    return report


def failed_watchdog(directory, reason):
    """Best-effort coordinator fallback; never makes a failed watchdog acceptable."""
    try:
        recovery = recover(directory)
    except Exception as error:
        recovery = {'recovery_required':True, 'error_type':type(error).__name__}
    report = {'scenario_passed':False, 'accepted':False, 'recovery_required':True,
        'watchdog_completed':False, 'reason':reason, 'fallback':recovery}
    publish(directory/'watchdog-failure.json', report)
    return report


def launch(directory, role, *args):
    # Windows venv python.exe is a redirector; use its base interpreter directly.
    with (directory/(role+'-stdout.log')).open('w') as out, (directory/(role+'-stderr.log')).open('w') as err:
        return subprocess.Popen([sys._base_executable, '-B', __file__, role, str(directory), *args],
            stdout=out, stderr=err, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def audit():
    output = ROOT / 'reports' / ('watchdog-' + uuid4().hex[:12])
    output.mkdir(parents=True)
    results=[]
    for scenario in ('complete','timeout','crash','unresponsive'):
        directory=output/scenario
        directory.mkdir()
        (directory/'fixture.txt').write_text('harmless readonly fixture\n', encoding='utf-8', newline='')
        start=time.monotonic()
        manifest={'name':'ayursage-controls-watch-'+uuid4().hex[:12], 'token':uuid4().hex,
            'start':start,'deadline':start+35,'terminate_at':start+25,'scenario':scenario,'image':IMAGE}
        save(directory/'manifest.json', manifest)
        watchdog=launch(directory, 'watch')
        publish(directory/'watchdog-launch.json', {'pid':watchdog.pid, 'parent_pid':os.getpid(),
            'namespace':'windows-host' if os.name == 'nt' else 'host', 'executable':sys._base_executable})
        supervisor=launch(directory, 'supervise', scenario)
        while time.monotonic()<start+40 and watchdog.poll() is None:
            time.sleep(0.1)
        # Stop the creator first so recovery cannot race a later worker start.
        if supervisor.poll() is None:
            if scenario != 'unresponsive' and watchdog.poll() is not None:
                try:
                    supervisor.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    supervisor.terminate()
            else:
                supervisor.terminate()
        supervisor.wait(timeout=3)
        save(directory/'supervisor-finished.json', {'exit_code':supervisor.returncode})
        if watchdog.poll() is None:
            watchdog.terminate()
            watchdog.wait(timeout=3)
            report=failed_watchdog(directory, 'WATCHDOG_STALLED')
        else:
            try:
                report=completion(directory,manifest,watchdog,supervisor.returncode)
                if not report['scenario_passed']:
                    report['fallback']=failed_watchdog(directory,'FINAL_ACCEPTANCE_FAILED')
            except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
                report=failed_watchdog(directory,type(error).__name__)
        report['scenario']=scenario
        results.append(report)
        accepted=all(r.get('scenario_passed') is True for r in results) and len(results)==4
        save(output/'results.json', {'results':results,'audit_accepted':accepted,
            'real_daemon_loss_tested':False,'model_access':False,'containers_retained':True})
        if not report['scenario_passed']:
            print(json.dumps({'output':str(output),'audit_accepted':False,'results':results},indent=2))
            return 1
    print(json.dumps({'output':str(output),'audit_accepted':accepted,'results':results},indent=2))
    return 0 if accepted else 1


if __name__ == '__main__':
    if len(sys.argv)==1:
        raise SystemExit(audit())
    elif sys.argv[1]=='watch':
        raise SystemExit(watch(sys.argv[2]))
    elif sys.argv[1]=='supervise':
        raise SystemExit(supervise(sys.argv[2],sys.argv[3]))
    elif sys.argv[1]=='recover':
        print(json.dumps(recover(sys.argv[2])))
    else:
        raise SystemExit('Unsupported harmless audit command')
