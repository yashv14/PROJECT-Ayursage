"""Bounded harmless diagnostic evidence; no ML dependencies or execution."""

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
from queue import Queue, Full
from threading import Thread
import sys
import time

# Windows CreateFile share mode that still allows Path.replace() of the target.
_FILE_SHARE_READ_WRITE_DELETE = 0x1 | 0x2 | 0x4
_GENERIC_READ = 0x80000000
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x80
_NT_KERNEL = None


def _nt_file_api():
    global _NT_KERNEL
    if _NT_KERNEL is None:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        _NT_KERNEL = kernel
    return _NT_KERNEL


@contextmanager
def hold_published_read(path, *, share=_FILE_SHARE_READ_WRITE_DELETE):
    """Hold an open read handle. Default sharing allows concurrent atomic replace."""
    import ctypes
    from ctypes import wintypes
    kernel = _nt_file_api()
    handle = kernel.CreateFileW(str(path), _GENERIC_READ, share, None,
        _OPEN_EXISTING, _FILE_ATTRIBUTE_NORMAL, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield handle
    finally:
        kernel.CloseHandle(handle)


def _nt_read_handle(handle):
    import ctypes
    from ctypes import wintypes
    kernel = _nt_file_api()
    chunks = []
    while True:
        buffer = ctypes.create_string_buffer(4096)
        count = wintypes.DWORD()
        if not kernel.ReadFile(handle, buffer, 4096, ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value == 0:
            break
        chunks.append(buffer.raw[:count.value])
    return b''.join(chunks).decode('utf-8')


def read_published_text(path):
    """Read published heartbeat text without denying Windows Path.replace()."""
    path = Path(path)
    if os.name != 'nt':
        return path.read_text(encoding='utf-8')
    with hold_published_read(path) as handle:
        return _nt_read_handle(handle)


def host_identity():
    info = time.get_clock_info('monotonic')
    return {'pid':os.getpid(), 'ppid':os.getppid(), 'executable':sys.executable,
        'platform':sys.platform, 'clock_domain':'windows-host-boot' if os.name == 'nt' else 'host-boot',
        'clock_implementation':info.implementation}


def bounded_evidence_write(write, *, timeout=0.5):
    """Bound the caller's wait; never claim a stuck filesystem write completed."""
    result = []
    def attempt():
        try:
            write()
            result.append(True)
        except Exception:
            result.append(False)
    thread = Thread(target=attempt, daemon=True)
    thread.start()
    thread.join(timeout)
    return not thread.is_alive() and result == [True]


class EvidenceLog:
    """Nonblocking enqueue; bounded records/bytes; bounded final drain.

    A stuck daemon writer cannot block the control loop. Failure is sticky. This
    does not bound unrelated final-result filesystem operations or host stalls.
    """
    def __init__(self, path, *, limit=1024, writer=None):
        self.path = Path(path)
        self.limit = limit
        self.count = 0
        self.incomplete = False
        self.queue = Queue(maxsize=32)
        self.writer = writer or self._write
        self.thread = Thread(target=self._consume, daemon=True)
        self.thread.start()

    def _write(self, line):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')

    def _consume(self):
        try:
            while True:
                line = self.queue.get()
                if line is None:
                    return
                self.writer(line)
        except Exception:
            self.incomplete = True

    def record(self, event):
        try:
            line = json.dumps(event, allow_nan=False)
        except (TypeError, ValueError):
            self.incomplete = True
            return
        if self.count >= self.limit or len(line.encode('utf-8')) > 8192:
            self.incomplete = True
            return
        self.count += 1
        try:
            self.queue.put_nowait(line)
        except Full:
            self.incomplete = True

    def finish(self, timeout=0.5):
        try:
            self.queue.put_nowait(None)
        except Full:
            self.incomplete = True
        self.thread.join(timeout)
        self.incomplete |= self.thread.is_alive()
        return not self.incomplete


class HeartbeatError(RuntimeError):
    pass


class Heartbeat:
    def __init__(self, path, manifest, log, *, clock=time.monotonic, sleep=time.sleep):
        self.path = Path(path)
        self.manifest = manifest
        self.log = log
        self.clock = clock
        self.sleep = sleep
        self.identity = host_identity()
        self.last = None

    def event(self, kind, **values):
        self.log.record({'event':kind, 'run_id':self.manifest['token'],
            'scenario_id':self.manifest['scenario'], 'identity':self.identity, **values})

    def write(self):
        before = self.clock()
        value = {'format':'ayursage-heartbeat-v1', 'monotonic':before,
            'run_id':self.manifest['token'], 'scenario_id':self.manifest['scenario'],
            'writer':self.identity}
        temporary = self.path.with_suffix('.pending')
        paths = {'source_path':str(temporary), 'target_path':str(self.path)}
        # One immutable value per write call. A retry cannot advance its timestamp.
        deadline = self.manifest.get('deadline', float('inf'))
        until = min(deadline, before + 0.2)
        def record(phase, attempt, outcome, retry_outcome, error=None, operation_started=None):
            self.event('heartbeat_write', before=before, after=self.clock(), value=value,
                attempt_before=before if operation_started is None else operation_started,
                operation_phase=phase, attempt=attempt, outcome=outcome,
                retry_outcome=retry_outcome, exception_type=type(error).__name__ if error else None,
                errno=getattr(error,'errno',None), winerror=getattr(error,'winerror',None), **paths)
        if before >= until:
            record('deadline_check',0,'error','deadline_exhausted')
            raise HeartbeatError('HEARTBEAT_PUBLICATION_DEADLINE_EXHAUSTED')
        try:
            temporary.write_text(json.dumps(value), encoding='utf-8')
        except Exception as error:
            record('pending_write',1,'error','not_retryable',error)
            raise HeartbeatError('HEARTBEAT_WRITE_ERROR') from error
        last_error = None
        for attempt in range(1,4):
            if self.clock() >= until or getattr(self.log,'incomplete',False):
                record('deadline_check',attempt,'error','deadline_or_evidence_exhausted',last_error)
                raise HeartbeatError('HEARTBEAT_PUBLICATION_DEADLINE_OR_EVIDENCE_EXHAUSTED') from last_error
            started = self.clock()
            try:
                temporary.replace(self.path)
            except Exception as error:
                last_error = error
                # These errors may be transient on Windows; their native cause is unknown.
                retryable = isinstance(error,OSError) and getattr(error,'winerror',None) in (5,32,33)
                retry = retryable and attempt < 3 and self.clock() + 0.025 < until
                record('replace',attempt,'error','retry_scheduled' if retry else 'rejected',error,started)
                if not retry:
                    raise HeartbeatError('HEARTBEAT_PUBLICATION_FAILED') from error
                self.sleep(0.025)
                continue
            if self.clock() >= deadline:
                record('replace',attempt,'error','published_after_deadline',operation_started=started)
                raise HeartbeatError('HEARTBEAT_PUBLICATION_DEADLINE_EXHAUSTED')
            record('replace',attempt,'ok','published',operation_started=started)
            if getattr(self.log,'incomplete',False):
                raise HeartbeatError('HEARTBEAT_EVIDENCE_INCOMPLETE')
            return

    def read(self, *, threshold=3):
        before = self.clock()
        value = None
        # Bounded retries for transient Windows file-sharing conflicts on the
        # published file only. JSON parse errors, schema errors, and unrelated
        # I/O errors are fatal and never retried. The retry window must complete
        # before the deadline. The Windows reader opens with delete sharing so
        # it does not itself deny the writer's atomic replace.
        deadline = self.manifest.get('deadline', float('inf'))
        last_read_error = None
        for read_attempt in range(1, 4):
            try:
                raw = read_published_text(self.path)
                last_read_error = None
                break
            except OSError as error:
                retryable = getattr(error, 'winerror', None) in (5, 32, 33)
                retry = retryable and read_attempt < 3 and self.clock() + 0.025 < deadline
                self.event('heartbeat_read', before=before, after=self.clock(),
                    value=None, age=None, threshold=threshold, outcome='error',
                    exception_type=type(error).__name__, recovery_decision=not retry,
                    operation_phase='read_transient_attempt',
                    target_path=str(self.path), attempt=read_attempt,
                    retry_outcome='retry_scheduled' if retry else 'rejected',
                    errno=getattr(error, 'errno', None),
                    winerror=getattr(error, 'winerror', None),
                    reason='heartbeat_observation_unavailable')
                if not retry:
                    last_read_error = error
                    break
                last_read_error = error
                self.sleep(0.025)
        if last_read_error is not None:
            raise HeartbeatError('HEARTBEAT_OBSERVATION_UNAVAILABLE') from last_read_error
        try:
            value = json.loads(raw)
            after = self.clock()
            stamp = value['monotonic']
            if (value['format'] != 'ayursage-heartbeat-v1'
                    or value['run_id'] != self.manifest['token']
                    or value['scenario_id'] != self.manifest['scenario']
                    or value['writer']['clock_domain'] != self.identity['clock_domain']
                    or value['writer']['clock_implementation'] != self.identity['clock_implementation']
                    or type(stamp) not in (int,float) or not math.isfinite(stamp)
                    or stamp < self.manifest['start'] or stamp > after
                    or after >= self.manifest.get('deadline',float('inf'))
                    or after < before or (self.last is not None and stamp < self.last)):
                raise ValueError('INCONSISTENT_HEARTBEAT')
            self.last = stamp
            age = after-stamp
            self.event('heartbeat_read', before=before, after=after, value=value,
                age=age, threshold=threshold, outcome='ok',
                recovery_decision=age >= threshold,
                reason='supervisor_unresponsive' if age >= threshold else 'fresh')
            return stamp
        except Exception as error:
            self.event('heartbeat_read', before=before, after=self.clock(), value=value,
                age=None, threshold=threshold, outcome='error',
                exception_type=type(error).__name__, recovery_decision=True,
                operation_phase='read_or_parse', target_path=str(self.path),
                errno=getattr(error,'errno',None), winerror=getattr(error,'winerror',None),
                reason='heartbeat_observation_unavailable')
            raise HeartbeatError('HEARTBEAT_OBSERVATION_UNAVAILABLE') from error


def matching_alive(reference, observation):
    """Require same boot, namespace, PID, start ticks and parent relationship."""
    try:
        old, new = reference['processes'], observation['processes']
        if (len(old) != 2 or len(new) != 2 or not reference['boot_id']
                or reference['boot_id'] != observation['boot_id']):
            return False
        for previous, current in zip(old,new):
            if any(previous[key] != current[key] for key in ('pid','ppid','start_ticks','pid_namespace')):
                return False
            if current['state'] not in ('R','S','D','T','t','I','W','P'):
                return False
            if (type(current['pid']) is not int or current['pid'] <= 0
                    or type(current['start_ticks']) is not int or current['start_ticks'] <= 0
                    or current['pid_namespace'] != observation['observer']['pid_namespace']
                    or previous['pid_namespace'] != reference['observer']['pid_namespace']):
                return False
        return new[1]['ppid'] == new[0]['pid']
    except (KeyError, TypeError):
        return False


def classify_tracked_termination(before, observation, *, container_exited=False):
    """Validate supplied exit evidence only; no observer or PID descriptors are opened.

    An actual collector must validate its namespace and survive worker exit before
    supplying evidence. Synthetic records in tests are not runtime verification.
    """
    result = {'container_exited':container_exited is True,
        'parent_termination_verified':False, 'child_termination_verified':False,
        'accepted':False, 'recovery_required':True, 'reason':'observation_unavailable'}
    if not matching_alive(before,before):
        result['reason']='invalid_precondition'
        return result
    try:
        if observation['outcome'] != 'ok':
            result['reason']='observer_' + observation['outcome']
            return result
        if observation['observer_validated'] is not True or observation['survives_worker_exit'] is not True:
            return result
        if observation['boot_id'] != before['boot_id'] or observation['target_pid_namespace'] != before['processes'][0]['pid_namespace']:
            result['reason']='wrong_namespace_or_boot'
            return result
        exits=observation['processes']
        if len(exits)!=2:
            return result
        for old,new in zip(before['processes'],exits):
            if any(old[key]!=new[key] for key in ('pid','ppid','start_ticks','pid_namespace')):
                result['reason']='identity_mismatch'
                return result
        parent,child=(entry['terminated'] is True for entry in exits)
        result.update(parent_termination_verified=parent, child_termination_verified=child,
            accepted=container_exited is True and parent and child,
            recovery_required=not (container_exited is True and parent and child),
            reason='tracked_exits_observed' if parent and child else 'tracked_process_still_alive')
    except (KeyError,TypeError):
        pass
    return result
