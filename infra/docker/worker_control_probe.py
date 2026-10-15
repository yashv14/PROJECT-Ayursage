"""Harmless restriction probe. No model, training source or ML dependencies."""

import errno
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def process_identity(pid):
    stat = Path('/proc/' + str(pid) + '/stat').read_text()
    fields = stat.rsplit(')', 1)[1].split()
    return {'pid':pid, 'ppid':int(fields[1]), 'state':fields[0],
        'start_ticks':int(fields[19]), 'raw_stat':stat,
        'pid_namespace':os.readlink('/proc/' + str(pid) + '/ns/pid'),
        'mount_namespace':os.readlink('/proc/' + str(pid) + '/ns/mnt')}


def observe_processes(pids):
    return {'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'observer':process_identity(os.getpid()),
        'processes':[process_identity(pid) for pid in pids]}


def controls():
    assert Path('/inputs/fixture.txt').read_text() == 'harmless readonly fixture\n'
    for path in (Path('/inputs/fixture.txt'), Path('/probe.py'), Path('/root-write-test')):
        try:
            with path.open('ab'):
                pass
        except OSError as error:
            assert error.errno in (errno.EROFS, errno.EACCES)
        else:
            raise AssertionError('Unexpected writable input/root')
    scratch = Path('/scratch/check.txt')
    scratch.write_text('scratch only')
    assert scratch.read_text() == 'scratch only'
    interfaces = sorted(p.name for p in Path('/sys/class/net').iterdir())
    assert interfaces == ['lo'], interfaces
    assert not any(line.split()[1] == '00000000' for line in Path('/proc/net/route').read_text().splitlines()[1:])
    for kind, port in ((socket.SOCK_STREAM, 80), (socket.SOCK_DGRAM, 53)):
        with socket.socket(socket.AF_INET, kind) as connection:
            connection.settimeout(1)
            try:
                if kind == socket.SOCK_STREAM:
                    connection.connect(('192.0.2.1', port))
                else:
                    connection.sendto(b'harmless DNS transport probe', ('192.0.2.1', port))
            except OSError as error:
                assert error.errno == errno.ENETUNREACH, (kind, error.errno)
            else:
                raise AssertionError('Unexpected external network route')
    allowed = {'PATH','LANG','GPG_KEY','PYTHON_VERSION','PYTHON_SHA256','HOSTNAME','HOME','TMPDIR','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS'}
    assert set(os.environ) <= allowed, sorted(set(os.environ) - allowed)
    assert not Path('/var/run/docker.sock').exists()
    print(json.dumps({'controls': 'passed', 'interfaces': interfaces, 'uid': os.getuid()}), flush=True)
    print('harmless stderr captured', file=sys.stderr, flush=True)


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'controls':
        controls()
    elif mode == 'failure':
        print('intentional harmless exit 7', flush=True)
        print('intentional failure stderr', file=sys.stderr, flush=True)
        sys.exit(7)
    elif mode == 'timeout':
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c',
            "import os,time; print('CHILD_STARTED:'+str(os.getpid()),flush=True); time.sleep(300)"])
        print('PARENT_STARTED:' + str(os.getpid()), flush=True)
        print('CHILD_PID:' + str(child.pid), flush=True)
        identity = observe_processes([os.getpid(),child.pid])
        Path('/scratch/process-identities.json').write_text(json.dumps(identity))
        print('PROCESS_IDENTITIES:' + json.dumps(identity), flush=True)
        time.sleep(300)
    elif mode == 'observe':
        reference = json.loads(Path('/scratch/process-identities.json').read_text())
        print(json.dumps(observe_processes([p['pid'] for p in reference['processes']])), flush=True)
    else:
        raise SystemExit('unsupported harmless probe mode')
