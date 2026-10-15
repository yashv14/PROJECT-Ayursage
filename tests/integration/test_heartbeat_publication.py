"""Focused publication tests: opaque temporary JSON only; no Docker or ML."""

import errno
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'infra/docker'))
import worker_diagnostics
from worker_diagnostics import Heartbeat, HeartbeatError, hold_published_read, read_published_text
import test_worker_watchdog as existing
import test_worker_diagnostics as diagnostics


class PublicationTests(unittest.TestCase):
    def fixture(self, directory):
        clock=existing.Clock(); clock.now=9
        records=diagnostics.Records()
        hb=Heartbeat(Path(directory)/'heartbeat.json',
            {'token':'test','scenario':'focused','start':0,'deadline':20},records,
            clock=clock,sleep=clock.sleep)
        hb.write(); records.records.clear(); clock.now=10
        return hb,clock,records

    def locked(self):
        error=PermissionError(errno.EACCES,'simulated replacement denial')
        error.winerror=5
        return error

    def test_successful_publication_preserves_phase_paths_and_timestamp(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.write()
            event=records.records[-1]
            self.assertEqual(event['operation_phase'],'replace')
            self.assertEqual(event['attempt'],1); self.assertEqual(event['retry_outcome'],'published')
            self.assertEqual(event['source_path'],str(hb.path.with_suffix('.pending')))
            self.assertEqual(event['target_path'],str(hb.path))
            self.assertEqual(hb.read(),10)

    def test_transient_replace_failure_retries_same_value(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); original=Path.replace; calls=[]
            def replace(path,target):
                calls.append(path)
                if len(calls)==1:
                    self.assertEqual(json.loads(hb.path.read_text())['monotonic'],9)
                    raise self.locked()
                return original(path,target)
            with patch.object(Path,'replace',replace): hb.write()
            first,last=records.records
            self.assertEqual(first['errno'],errno.EACCES); self.assertEqual(first['winerror'],5)
            self.assertEqual(first['retry_outcome'],'retry_scheduled')
            self.assertEqual(last['attempt'],2); self.assertEqual(last['retry_outcome'],'published')
            self.assertEqual(first['value'],last['value'])
            self.assertEqual(hb.read(),10)
            self.assertGreater(clock(),10)

    def test_persistent_replace_failure_never_advances_published_value(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            with patch.object(Path,'replace',side_effect=self.locked()) as replacement:
                with self.assertRaises(HeartbeatError): hb.write()
            self.assertEqual(replacement.call_count,3)
            self.assertEqual(hb.read(),9)
            self.assertEqual(json.loads(hb.path.with_suffix('.pending').read_text())['monotonic'],10)
            self.assertEqual(records.records[-2]['retry_outcome'],'rejected')

    def test_retry_deadline_exhaustion_stops_without_second_attempt(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.manifest['deadline']=10.1
            hb.sleep=lambda seconds:clock.sleep(0.2)
            with patch.object(Path,'replace',side_effect=self.locked()) as replacement:
                with self.assertRaisesRegex(HeartbeatError,'DEADLINE'): hb.write()
            self.assertEqual(replacement.call_count,1)
            self.assertEqual(json.loads(hb.path.read_text())['monotonic'],9)
            self.assertEqual(records.records[-1]['operation_phase'],'deadline_check')
            with self.assertRaises(HeartbeatError): hb.read()

    def test_expired_deadline_prevents_pending_write(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.manifest['deadline']=10
            with patch.object(Path,'write_text') as writing:
                with self.assertRaisesRegex(HeartbeatError,'DEADLINE'): hb.write()
            writing.assert_not_called()

    def test_unrecognized_error_is_not_retried(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            with patch.object(Path,'replace',side_effect=PermissionError()) as replacement:
                with self.assertRaises(HeartbeatError): hb.write()
            self.assertEqual(replacement.call_count,1)

    def test_publication_finishing_after_global_deadline_remains_rejected(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.manifest['deadline']=10.1
            original=Path.replace
            def late(path,target):
                clock.sleep(0.2)
                return original(path,target)
            with patch.object(Path,'replace',late):
                with self.assertRaisesRegex(HeartbeatError,'DEADLINE'): hb.write()
            with self.assertRaises(HeartbeatError): hb.read()
            self.assertEqual(records.records[-2]['retry_outcome'],'published_after_deadline')

    @unittest.skipUnless(os.name=='nt','Requires Windows file-sharing semantics')
    def test_concurrent_windows_reader_denies_then_releases_replacement(self):
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
            ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.ReadFile.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        ready,release,closed=Event(),Event(),Event(); errors=[]
        with TemporaryDirectory() as directory:
            records=diagnostics.Records()
            hb=Heartbeat(Path(directory)/'heartbeat.json',
                {'token':'native-test','scenario':'focused','start':0,'deadline':time.monotonic()+5},records)
            hb.write(); records.records.clear()
            def reader():
                handle=kernel.CreateFileW(str(hb.path),0x80000000,3,None,3,0x80,None)
                try:
                    if handle==ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
                    buffer=ctypes.create_string_buffer(4096); count=wintypes.DWORD()
                    if not kernel.ReadFile(handle,buffer,4096,ctypes.byref(count),None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    json.loads(buffer.raw[:count.value])
                    ready.set(); release.wait(2)
                except Exception as error:
                    errors.append(error); ready.set()
                finally:
                    kernel.CloseHandle(handle); closed.set()
            thread=Thread(target=reader,daemon=True); thread.start()
            try:
                self.assertTrue(ready.wait(1)); self.assertFalse(errors)
                def allow_retry(seconds):
                    release.set()
                    if not closed.wait(1): raise RuntimeError('reader did not close')
                    time.sleep(seconds)
                hb.sleep=allow_retry
                hb.write()
                self.assertEqual(records.records[0]['outcome'],'error')
                self.assertIn(records.records[0]['winerror'],(5,32,33))
                self.assertEqual(records.records[-1]['outcome'],'ok')
                self.assertEqual(records.records[0]['value'],records.records[-1]['value'])
            finally:
                release.set(); thread.join(2)

    @unittest.skipUnless(os.name=='nt','Requires Windows file-sharing semantics')
    def test_share_delete_reader_allows_replace_on_first_attempt(self):
        """Production read sharing must not force a replace retry."""
        with TemporaryDirectory() as directory:
            records=diagnostics.Records()
            hb=Heartbeat(Path(directory)/'heartbeat.json',
                {'token':'native-share-delete','scenario':'focused','start':0,
                 'deadline':time.monotonic()+5},records)
            hb.write(); records.records.clear()
            with hold_published_read(hb.path):
                hb.write()
            phases=[e for e in records.records if e.get('operation_phase')=='replace']
            self.assertEqual(len(phases),1)
            self.assertEqual(phases[0]['outcome'],'ok')
            self.assertEqual(phases[0]['attempt'],1)
            self.assertEqual(phases[0]['retry_outcome'],'published')
            self.assertIsNone(phases[0].get('winerror'))

    @unittest.skipUnless(os.name=='nt','Requires Windows file-sharing semantics')
    def test_heartbeat_read_overlapping_replace_keeps_atomic_publication(self):
        """Heartbeat.read() may overlap write(); replace stays atomic and bounded."""
        stop=Event(); errors=[]; stamps=[]
        with TemporaryDirectory() as directory:
            records=diagnostics.Records()
            hb=Heartbeat(Path(directory)/'heartbeat.json',
                {'token':'native-overlap','scenario':'focused','start':0,
                 'deadline':time.monotonic()+8},records)
            hb.write(); first=json.loads(hb.path.read_text(encoding='utf-8'))['monotonic']
            def reader():
                other=Heartbeat(hb.path,hb.manifest,diagnostics.Records())
                try:
                    while not stop.is_set():
                        stamps.append(other.read())
                        time.sleep(0)
                except Exception as error:
                    errors.append(error)
            thread=Thread(target=reader,daemon=True); thread.start()
            try:
                time.sleep(0.02)
                records.records.clear()
                hb.write()
                replace_events=[e for e in records.records if e.get('operation_phase')=='replace']
                self.assertTrue(replace_events)
                self.assertEqual(replace_events[-1]['outcome'],'ok')
                self.assertEqual(replace_events[0]['value'],replace_events[-1]['value'])
                published=json.loads(hb.path.read_text(encoding='utf-8'))
                self.assertEqual(published['format'],'ayursage-heartbeat-v1')
                self.assertGreaterEqual(published['monotonic'],first)
            finally:
                stop.set(); thread.join(2)
            self.assertFalse(errors)
            self.assertTrue(stamps)


class ReadRetryTests(unittest.TestCase):
    """Issue 1 — bounded read retries for transient Windows file-sharing conflicts."""

    def _locked_oserror(self, winerror_code=5):
        error = PermissionError('simulated sharing violation')
        error.winerror = winerror_code
        error.errno = 13
        return error

    def fixture(self, directory):
        clock=existing.Clock(); clock.now=9
        records=diagnostics.Records()
        hb=Heartbeat(Path(directory)/'heartbeat.json',
            {'token':'test','scenario':'focused','start':0,'deadline':20},records,
            clock=clock,sleep=clock.sleep)
        hb.write(); records.records.clear(); clock.now=10
        return hb,clock,records

    def test_transient_read_conflict_retried_and_succeeds(self):
        """A single transient winerror-5 on read_published_text() is retried; second attempt succeeds."""
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            original=read_published_text; calls=[]
            def flaky(path):
                calls.append(path)
                if len(calls)==1: raise self._locked_oserror(5)
                return original(path)
            with patch.object(worker_diagnostics,'read_published_text',flaky): stamp=hb.read()
        self.assertEqual(stamp,9)
        self.assertEqual(len(calls),2)
        # First event: transient attempt logged as error with retry_scheduled
        transient=[e for e in records.records if e.get('operation_phase')=='read_transient_attempt']
        self.assertEqual(len(transient),1)
        self.assertEqual(transient[0]['winerror'],5)
        self.assertEqual(transient[0]['retry_outcome'],'retry_scheduled')
        self.assertFalse(transient[0]['recovery_decision'])
        # Final success logged via normal ok path
        ok=[e for e in records.records if e.get('outcome')=='ok']
        self.assertEqual(len(ok),1)

    def test_persistent_read_conflict_fails_after_three_attempts(self):
        """Persistent winerror-5 on all read attempts raises HeartbeatError."""
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            calls=[]
            def always_locked(path):
                calls.append(path)
                raise self._locked_oserror(5)
            with patch.object(worker_diagnostics,'read_published_text',always_locked):
                with self.assertRaises(HeartbeatError): hb.read()
        self.assertEqual(len(calls),3)
        transient=[e for e in records.records if e.get('operation_phase')=='read_transient_attempt']
        self.assertEqual(len(transient),3)
        self.assertEqual(transient[-1]['retry_outcome'],'rejected')
        self.assertTrue(transient[-1]['recovery_decision'])

    def test_non_retryable_oserror_fails_immediately(self):
        """An OSError without a Windows sharing-violation winerror is not retried."""
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            calls=[]
            def unshared(path):
                calls.append(path)
                raise PermissionError('unrelated permission error')
            with patch.object(worker_diagnostics,'read_published_text',unshared):
                with self.assertRaises(HeartbeatError): hb.read()
        self.assertEqual(len(calls),1,'Non-retryable error must not be retried')

    def test_read_deadline_exhaustion_stops_retry_before_third_attempt(self):
        """If the deadline expires after the first retry sleep, the second retry is skipped."""
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            hb.manifest['deadline']=10.01  # Expires after first sleep(0.025) advances clock
            calls=[]
            def locked(path):
                calls.append(path)
                raise self._locked_oserror(5)
            with patch.object(worker_diagnostics,'read_published_text',locked):
                with self.assertRaises(HeartbeatError): hb.read()
        # Only 1 attempt should be made: clock+0.025 >= deadline after first failure
        self.assertLessEqual(len(calls),2,'Deadline must stop retries early')

    def test_json_parse_error_is_never_retried(self):
        """JSONDecodeError from parsing is fatal; the published-file read itself succeeded."""
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            hb.path.write_text('{bad json', encoding='utf-8')
            with self.assertRaises(HeartbeatError): hb.read()
        error_events=[e for e in records.records if e.get('outcome')=='error']
        self.assertEqual(len(error_events),1)
        self.assertEqual(error_events[0]['exception_type'],'JSONDecodeError')

    def test_winerror_32_and_33_are_also_retried(self):
        """winerror 32 (sharing violation) and 33 (lock violation) are also retried."""
        for winerror_code in (32, 33):
            with self.subTest(winerror=winerror_code), TemporaryDirectory() as directory:
                hb,clock,records=self.fixture(directory)
                original=read_published_text; calls=[]
                def flaky(path):
                    calls.append(path)
                    if len(calls)==1: raise self._locked_oserror(winerror_code)
                    return original(path)
                with patch.object(worker_diagnostics,'read_published_text',flaky): stamp=hb.read()
                self.assertEqual(stamp,9)
                records.records.clear()


if __name__=='__main__': unittest.main()
