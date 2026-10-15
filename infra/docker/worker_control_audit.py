"""Windows-host harmless Docker audit. Retains all containers; never mounts ML files.

Only the fixed probe below can run. Docker image must already be present.
This supervisor tests normal/timeout behavior, not daemon-loss recovery.
"""

import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258'


def docker(*args, check=True, timeout=10):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('Docker command failed: ' + args[0])
    return result


def inspect(cid):
    return json.loads(docker('inspect', cid).stdout)[0]


def create_worker(mode, name, fixture, *, command_timeout=10):
    """Create only the fixed harmless probe, with explicit ownership labels."""
    if mode not in ('controls', 'failure', 'timeout') or not name.startswith('ayursage-controls-'):
        raise ValueError('Unsupported harmless worker')
    probe = ROOT / 'infra/docker/worker_control_probe.py'
    return docker('create', '--pull', 'never', '--name', name,
        '--label', 'ayursage.harmless-audit=true', '--label', 'ayursage.audit-name=' + name,
        '--network', 'none', '--read-only', '--user', '1000:1000', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges=true', '--pids-limit', '64',
        '--memory', '256m', '--cpus', '1', '--restart', 'no',
        '--log-driver', 'local', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=1', '--log-opt', 'compress=false',
        '--tmpfs', '/scratch:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700',
        '--workdir', '/scratch', '--env', 'HOME=/scratch', '--env', 'TMPDIR=/scratch',
        '--env', 'OMP_NUM_THREADS=1', '--env', 'OPENBLAS_NUM_THREADS=1',
        '--mount', 'type=bind,source=' + str(fixture.resolve()) + ',target=/inputs/fixture.txt,readonly',
        '--mount', 'type=bind,source=' + str(probe) + ',target=/probe.py,readonly',
        '--entrypoint', 'python', IMAGE, '-I', '-B', '/probe.py', mode,
        timeout=command_timeout).stdout.strip()


def main():
    image = json.loads(docker('image', 'inspect', IMAGE).stdout)[0]
    assert image['Id'] == IMAGE
    run_id = uuid4().hex[:12]
    output = ROOT / 'reports' / ('worker-controls-' + run_id)
    output.mkdir(parents=True)
    fixture = output / 'fixture.txt'
    fixture.write_text('harmless readonly fixture\n', encoding='utf-8', newline='')
    results = []
    for mode in ('controls', 'failure', 'timeout'):
        name = 'ayursage-controls-' + run_id + '-' + mode
        cid = create_worker(mode, name, fixture)
        completed = False
        try:
            config = inspect(cid)
            host = config['HostConfig']
            assert host['NetworkMode'] == 'none' and host['ReadonlyRootfs']
            assert host['CapDrop'] == ['ALL'] and not host['Privileged']
            assert host['SecurityOpt'] == ['no-new-privileges=true']
            assert host['Memory'] == 256 * 1024 * 1024 and host['PidsLimit'] == 64
            assert config['Config']['User'] == '1000:1000'
            assert len(config['Mounts']) == 2
            assert {m['Destination'] for m in config['Mounts']} == {'/probe.py','/inputs/fixture.txt'}
            assert all(not m['RW'] for m in config['Mounts'])
            assert not host.get('PortBindings') and not host.get('Devices')
            budget = 5 if mode == 'timeout' else 20
            started = time.monotonic()
            docker('start', cid)
            timed_out = False
            child_host_pid = None
            while inspect(cid)['State']['Running']:
                if mode == 'timeout' and child_host_pid is None:
                    top = docker('top', cid, '-eo', 'pid,ppid,args').stdout
                    (output / (mode + '-processes.txt')).write_text(top, encoding='utf-8')
                    rows = top.splitlines()[1:]
                    if len(rows) >= 2:
                        child_host_pid = rows[-1].split()[0]
                if time.monotonic() - started >= budget:
                    docker('kill', '--signal', 'KILL', cid)
                    timed_out = True
                    break
                time.sleep(0.1)
            state = inspect(cid)['State']
            assert not state['Running']
            (output / (mode + '-state.json')).write_text(json.dumps({
                'container':name,'id':cid,'state':state}, indent=2), encoding='utf-8')
            logs = docker('logs', '--timestamps', cid)
            (output / (mode + '-stdout.log')).write_text(logs.stdout, encoding='utf-8')
            (output / (mode + '-stderr.log')).write_text(logs.stderr, encoding='utf-8')
            elapsed = time.monotonic() - started
            if mode == 'controls':
                assert state['ExitCode'] == 0 and '"controls": "passed"' in logs.stdout
                assert 'harmless stderr captured' in logs.stderr
            elif mode == 'failure':
                assert state['ExitCode'] == 7 and 'intentional failure stderr' in logs.stderr
            else:
                assert timed_out and child_host_pid and 'CHILD_STARTED:' in logs.stdout
                assert state['ExitCode'] == 137
                assert docker('top', cid, check=False).returncode != 0
            results.append({'mode':mode,'container':name,'id':cid,'exit_code':state['ExitCode'],
                'timed_out':timed_out,'elapsed_seconds':round(elapsed,3),
                'child_observed':bool(child_host_pid),'state_running':state['Running']})
            completed = True
        finally:
            # Never remove containers/volumes. Stop only our exact worker on failure.
            if not completed:
                docker('kill', '--signal', 'KILL', cid, check=False)
    report = {'image':IMAGE,'results':results,'output_directory':str(output),
        'model_mounted':False,'daemon_loss_recovery_tested':False,
        'supervisor_crash_recovery_tested':False,'containers_retained':True}
    (output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
