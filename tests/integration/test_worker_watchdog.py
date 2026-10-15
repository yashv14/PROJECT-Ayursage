"""Deterministic harmless fault injection: no Docker daemon or model execution."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra/docker'))
from worker_watchdog import (DockerWorker, monitor, outcome, recover, scenario_passed,
    publish, completion, failed_watchdog, descendants_disappeared, audit)
import os
import subprocess


class Clock:
    def __init__(self):
        self.now=0.0
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.now+=seconds


class Worker:
    def __init__(self, clock, complete_at=100):
        self.clock=clock
        self.complete_at=complete_at
        self.killed=False
        self.child_running=True
        self.kill_attempts=0
        self.unavailable=False
        self.kill_delay=0
        self.start_delay=0
    def state(self):
        if self.unavailable:
            raise RuntimeError('injected daemon unavailable')
        if self.start_delay:
            self.clock.sleep(self.start_delay)
            self.start_delay=0
        running=not self.killed and self.clock()<self.complete_at
        return {'Running':running,'Status':'running' if running else 'exited',
            'ExitCode':137 if self.killed else 0}
    def kill(self):
        self.kill_attempts+=1
        if self.unavailable:
            raise RuntimeError('injected daemon unavailable')
        self.clock.sleep(self.kill_delay)
        self.killed=True
        self.child_running=False
    def capture(self, directory):
        return self.state()


class WatchdogTests(unittest.TestCase):
    def run_monitor(self, worker, clock, heartbeat=None, capture=None):
        return monitor(worker,0,5,3,heartbeat or clock,capture or (lambda:None),
            clock=clock,sleep=clock.sleep)

    def test_completes_within_complete_operation_deadline(self):
        clock=Clock(); worker=Worker(clock,complete_at=1)
        result=self.run_monitor(worker,clock)
        self.assertTrue(result['accepted'])
        self.assertEqual(worker.kill_attempts,0)

    def test_pending_startup_does_not_trigger_premature_kill(self):
        clock=Clock(); worker=Worker(clock,complete_at=2)
        worker.ready=lambda:clock()>=1
        result=self.run_monitor(worker,clock)
        self.assertTrue(result['accepted'])
        self.assertEqual(worker.kill_attempts,0)

    def test_overlong_worker_is_stopped_in_termination_reserve(self):
        clock=Clock(); worker=Worker(clock)
        result=self.run_monitor(worker,clock)
        self.assertTrue(result['deadline_met'])
        self.assertTrue(worker.killed)
        self.assertFalse(worker.child_running)
        self.assertEqual(result['exit_code'],137)

    def test_unresponsive_supervisor_detected_independently(self):
        clock=Clock(); worker=Worker(clock)
        result=monitor(worker,0,10,8,lambda:0,lambda:None,clock=clock,sleep=clock.sleep)
        self.assertEqual(result['reason'],'supervisor_unresponsive')
        self.assertTrue(result['termination_confirmed'])

    def test_slow_termination_is_overrun_not_pass(self):
        clock=Clock(); worker=Worker(clock); worker.kill_delay=4
        result=self.run_monitor(worker,clock)
        self.assertTrue(result['deadline_exceeded'])
        self.assertTrue(result['termination_confirmed'])
        self.assertFalse(result['accepted'])

    def test_startup_overrun_is_not_hidden(self):
        clock=Clock(); worker=Worker(clock); worker.start_delay=6
        result=self.run_monitor(worker,clock)
        self.assertTrue(result['deadline_exceeded'])
        self.assertFalse(result['accepted'])

    def test_cleanup_overrun_is_not_hidden(self):
        clock=Clock(); worker=Worker(clock,complete_at=1)
        result=self.run_monitor(worker,clock,capture=lambda:clock.sleep(6))
        self.assertTrue(result['cleanup_completed'])
        self.assertTrue(result['deadline_exceeded'])
        self.assertFalse(result['accepted'])

    def test_daemon_loss_reports_unconfirmed_failure(self):
        clock=Clock(); worker=Worker(clock); worker.unavailable=True
        result=self.run_monitor(worker,clock)
        self.assertGreater(worker.kill_attempts,0)
        self.assertTrue(result['termination_unconfirmed'])
        self.assertTrue(result['recovery_required'])
        self.assertFalse(result['cleanup_completed'])
        self.assertFalse(result['accepted'])

    def test_capture_failure_requires_recovery(self):
        clock=Clock(); worker=Worker(clock,complete_at=1)
        def fail(): raise OSError('injected log write failure')
        result=self.run_monitor(worker,clock,capture=fail)
        self.assertTrue(result['termination_confirmed'])
        self.assertTrue(result['recovery_required'])
        self.assertFalse(result['accepted'])

    def test_confirmed_exit_alone_cannot_pass_late_cleanup(self):
        result=outcome(0,5,6,True,True)
        self.assertFalse(result['accepted'])
        self.assertTrue(result['deadline_exceeded'])

    def test_stale_recovery_does_not_restart_or_delete(self):
        clock=Clock(); worker=Worker(clock)
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'manifest.json').write_text(json.dumps({'name':'ayursage-controls-watch-fixture','scenario':'complete'}))
            with patch('worker_watchdog.DockerWorker',return_value=worker):
                result=recover(directory)
            self.assertTrue(result['termination_confirmed'])
            self.assertFalse(result['restarted'])
            self.assertFalse(result['deleted'])

    def test_daemon_loss_stale_recovery_keeps_uncertainty(self):
        clock=Clock(); worker=Worker(clock); worker.unavailable=True
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'manifest.json').write_text(json.dumps({'name':'ayursage-controls-watch-fixture','scenario':'complete'}))
            with patch('worker_watchdog.DockerWorker',return_value=worker):
                result=recover(directory)
            self.assertTrue(result['recovery_required'])
            self.assertFalse(result['termination_confirmed'])

    def test_unrelated_worker_labels_refused(self):
        worker=DockerWorker('ayursage-controls-watch-fixture')
        response=type('Response',(),{'stdout':json.dumps([{'Config':{'Labels':{}},'State':{}}])})()
        with patch.object(worker,'command',return_value=response) as command:
            with self.assertRaisesRegex(RuntimeError,'OWNERSHIP'):
                worker.kill()
            self.assertEqual(command.call_count,1)


class CompletionTests(unittest.TestCase):
    def valid(self):
        return dict(outcome(0,35,26,True,True), descendants_confirmed=True, container_exit_confirmed=True,
            diagnostics_complete=True,
            evidence_finalized=True, watchdog_completed=True, identity_verified=True,
            completion_deadline_met=True, terminal_state='FINAL', watchdog_exit=0,
            elapsed_seconds=26, completion_elapsed_seconds=27, budget_seconds=35,
            exit_code=137, supervisor_exit=0, scenario='timeout', reason='deadline_reserve')

    def test_expected_nonzero_worker_exit_can_pass(self):
        self.assertTrue(scenario_passed(self.valid()))

    def test_each_missing_required_field_fails(self):
        for key in self.valid():
            with self.subTest(key=key):
                value=self.valid(); del value[key]
                self.assertFalse(scenario_passed(value))

    def test_late_incomplete_contradictory_and_malformed_results_fail(self):
        changes={'accepted':False,'deadline_met':False,'deadline_exceeded':True,
            'termination_confirmed':False,'container_exit_confirmed':False,'termination_unconfirmed':True,
            'descendants_confirmed':False,'cleanup_completed':False,
            'evidence_finalized':False,'recovery_required':True,'watchdog_completed':False,
            'identity_verified':False,'completion_deadline_met':False,'terminal_state':'PRELIMINARY',
            'watchdog_exit':1,'elapsed_seconds':36,'completion_elapsed_seconds':40,
            'budget_seconds':float('nan'),'scenario':'unknown','exit_code':0,'supervisor_exit':1}
        for key,value in changes.items():
            with self.subTest(key=key):
                report=self.valid(); report[key]=value
                self.assertFalse(scenario_passed(report))
        for value in (1,'true',None):
            report=self.valid(); report['accepted']=value
            self.assertFalse(scenario_passed(report))

    def test_final_publication_never_overwrites(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/'result.json'; publish(path,{'first':True})
            with self.assertRaises(FileExistsError): publish(path,{'first':False})
            self.assertEqual(json.loads(path.read_text()),{'first':True})

    def fixture(self,directory,code=0,pid=42):
        report=self.valid(); report['token']='nonce'
        publish(directory/'result.json',report)
        publish(directory/'watchdog-ready.json',{'pid':pid,'ppid':os.getpid(),
            'token':'nonce','namespace':'windows-host' if os.name=='nt' else 'host'})
        publish(directory/'heartbeat-writer-status.json',{'complete':True})
        worker=type('Process',(),{'pid':42,'poll':lambda self:code})()
        manifest={'token':'nonce','scenario':'timeout','start':0,'deadline':35}
        return worker,manifest

    def test_handle_exit_and_identity_required(self):
        for code,pid in ((None,42),(1,42),(0,99)):
            with self.subTest(code=code,pid=pid), TemporaryDirectory() as temp:
                directory=Path(temp); worker,manifest=self.fixture(directory,code,pid)
                if code is None:
                    with self.assertRaisesRegex(RuntimeError,'NOT_COMPLETED'):
                        completion(directory,manifest,worker,0,clock=lambda:27)
                else:
                    self.assertFalse(completion(directory,manifest,worker,0,clock=lambda:27)['scenario_passed'])

    def test_missing_final_result_is_not_completion(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp); publish(directory/'preliminary.json',self.valid())
            worker=type('Process',(),{'poll':lambda self:0})()
            with self.assertRaises(FileNotFoundError): completion(directory,{},worker,0)

    def test_completion_receipt_and_deadline(self):
        for now,accepted in ((27,True),(36,False)):
            with self.subTest(now=now), TemporaryDirectory() as temp:
                directory=Path(temp); worker,manifest=self.fixture(directory)
                self.assertEqual(completion(directory,manifest,worker,0,clock=lambda:now)['scenario_passed'],accepted)
                self.assertIn('result_sha256',json.loads((directory/'completion.json').read_text()))

    def test_conflicting_result_rejected(self):
        with TemporaryDirectory() as temp:
            directory=Path(temp); worker,manifest=self.fixture(directory)
            original=publish
            def conflict(path,value):
                original(path,value)
                (directory/'result.json').write_text('{}')
            with patch('worker_watchdog.publish',side_effect=conflict):
                self.assertFalse(completion(directory,manifest,worker,0,clock=lambda:27)['scenario_passed'])

    def test_watchdog_failure_always_rejects_even_if_fallback_stops_worker(self):
        for reason in ('WATCHDOG_STALLED','WATCHDOG_CRASHED'):
            with self.subTest(reason=reason), TemporaryDirectory() as temp:
                with patch('worker_watchdog.recover',return_value={'termination_confirmed':True}) as fallback:
                    result=failed_watchdog(Path(temp),reason)
                fallback.assert_called_once()
                self.assertFalse(result['accepted']); self.assertTrue(result['recovery_required'])
                self.assertTrue((Path(temp)/'watchdog-failure.json').exists())

    def test_watchdog_and_daemon_failure_is_unconfirmed(self):
        with TemporaryDirectory() as temp:
            with patch('worker_watchdog.recover',side_effect=RuntimeError('unavailable')):
                result=failed_watchdog(Path(temp),'WATCHDOG_CRASHED')
            self.assertTrue(result['fallback']['recovery_required'])
            self.assertFalse(result['scenario_passed'])

    def test_coordinator_crashed_or_stalled_watchdog_returns_failure_and_recovers(self):
        class Process:
            pid=42
            def __init__(self, code): self.returncode=code
            def poll(self): return self.returncode
            def terminate(self): self.returncode=1
            def wait(self, timeout): return self.returncode
        for initial_code in (7, None):
            with self.subTest(exit=initial_code), TemporaryDirectory() as temp:
                clock=Clock(); watchdog=Process(initial_code); supervisor=Process(0)
                with patch('worker_watchdog.ROOT',Path(temp)), \
                        patch('worker_watchdog.launch',side_effect=[watchdog,supervisor]), \
                        patch('worker_watchdog.time.monotonic',clock), \
                        patch('worker_watchdog.time.sleep',clock.sleep), \
                        patch('worker_watchdog.recover',return_value={'recovery_required':True}) as recovery, \
                        patch('builtins.print'):
                    self.assertEqual(audit(),1)
                recovery.assert_called_once()
                report=json.loads(next(Path(temp).glob('reports/*/results.json')).read_text())
                self.assertFalse(report['audit_accepted'])
                self.assertFalse(report['results'][0]['scenario_passed'])
                if initial_code is None:
                    self.assertEqual(watchdog.returncode,1)

    def test_descendant_absence_requires_same_boot_and_observed_inventory(self):
        before={'namespace':'docker-desktop:/proc','pids':[10,11],'exit_code':0,
            'stdout':'boot-id\n10 (python) S 1 raw-stat\n11 (python) S 10 raw-stat\n','finished':1,
            'docker_top':'PID PPID COMMAND\n10 1 python probe\n11 10 python child\n'}
        after={'namespace':'docker-desktop:/proc','pids':[10,11],'exit_code':0,
            'stdout':'boot-id\nABSENT:10\nABSENT:11\n','monotonic':2}
        self.assertTrue(descendants_disappeared(before,after))
        for key,value in [('stdout','other-boot\nABSENT:10\nABSENT:11\n'),
                ('stdout','boot-id\nABSENT:10\n11 (python) still-present\n'),
                ('exit_code',1),('pids',[10]),('monotonic',0)]:
            changed=dict(after); changed[key]=value
            self.assertFalse(descendants_disappeared(before,changed))
        self.assertFalse(descendants_disappeared({},after))

    def test_absence_before_termination_cannot_prove_pid_namespace(self):
        before={'namespace':'docker-desktop:/proc','pids':[10,11],'exit_code':0,
            'stdout':'boot-id\nABSENT:10\nABSENT:11\n','finished':1,
            'docker_top':'PID PPID COMMAND\n10 1 python probe\n11 10 python child\n'}
        after=dict(before,monotonic=2)
        self.assertFalse(descendants_disappeared(before,after))

    def test_created_worker_remains_recovery_required(self):
        clock=Clock(); worker=Worker(clock)
        worker.state=lambda:{'Running':False,'Status':'created','ExitCode':0}
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'manifest.json').write_text(json.dumps({'name':'ayursage-controls-watch-fixture','scenario':'complete'}))
            (directory/'supervisor-finished.json').write_text('{"exit_code":1}')
            with patch('worker_watchdog.DockerWorker',return_value=worker):
                result=recover(directory)
            self.assertTrue(result['recovery_required'])
            self.assertFalse(result['termination_confirmed'])

    def test_stopped_container_without_required_descendants_is_unconfirmed(self):
        clock=Clock(); worker=Worker(clock,complete_at=0)
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            (directory/'manifest.json').write_text(json.dumps({'name':'ayursage-controls-watch-fixture','scenario':'timeout'}))
            with patch('worker_watchdog.DockerWorker',return_value=worker):
                result=recover(directory)
            self.assertTrue(result['recovery_required'])
            self.assertFalse(result['termination_confirmed'])

    def test_base_interpreter_handle_pid_matches_actual_process(self):
        child=subprocess.Popen([sys._base_executable,'-B','-c',
            'import os,json; print(json.dumps(dict(pid=os.getpid(),ppid=os.getppid())))'],
            stdout=subprocess.PIPE,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        output=child.communicate(timeout=5)[0]
        self.assertEqual(child.returncode,0)
        self.assertEqual(json.loads(output),{'pid':child.pid,'ppid':os.getpid()})

    # Issue 2 — identity contract tests

    def test_mismatched_pid_in_ready_json_sets_identity_verified_false(self):
        """completion() must set identity_verified=False when ready.json PID != Popen handle PID."""
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            # pid=99 does not match the Process stub whose pid=42
            worker,manifest=self.fixture(directory,code=0,pid=99)
            result=completion(directory,manifest,worker,0,clock=lambda:27)
        self.assertFalse(result['identity_verified'])
        self.assertFalse(result['scenario_passed'])

    def test_correct_pid_in_ready_json_sets_identity_verified_true(self):
        """completion() must set identity_verified=True when ready.json PID matches Popen handle."""
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            worker,manifest=self.fixture(directory,code=0,pid=42)
            result=completion(directory,manifest,worker,0,clock=lambda:27)
        self.assertTrue(result['identity_verified'])
        self.assertTrue(result['scenario_passed'])

    def test_identity_mismatch_cannot_produce_accepted_scenario(self):
        """A completion report with identity_verified=False must never be scenario_passed."""
        report=self.valid(); report['identity_verified']=False
        self.assertFalse(scenario_passed(report))


class DescendantObserverTests(unittest.TestCase):
    """Issue 3 — docker-top based descendant termination evidence format tests."""

    def _before(self, container_id='abc123', pids=None, parents=None):
        """Build a valid docker-top format pre-termination record."""
        if pids is None:
            pids = [10, 11]
        if parents is None:
            parents = {10: 1, 11: 10}  # 11 is child of 10, 10 is child of init(1)
        return {
            'mechanism': 'docker_top',
            'container_id': container_id,
            'container_name': 'ayursage-controls-watch-test',
            'pids': list(pids),
            'docker_top': 'PID PPID COMMAND\n10 1 python probe\n11 10 python child\n',
            'parents': dict(parents),
            'monotonic': 1.0,
            'finished': 1.5,
        }

    def _after(self, container_id='abc123', pids=None, top_failed=True,
               container_exited=True, monotonic=2.0):
        if pids is None:
            pids = [10, 11]
        return {
            'mechanism': 'docker_top_absent',
            'container_id': container_id,
            'pids': list(pids),
            'top_failed': top_failed,
            'container_exited': container_exited,
            'monotonic': monotonic,
        }

    def test_valid_docker_top_evidence_confirms_descendants(self):
        self.assertTrue(descendants_disappeared(self._before(), self._after()))

    def test_docker_top_still_succeeds_post_kill_rejects(self):
        """If docker top succeeds after kill, the container is still running: reject."""
        self.assertFalse(descendants_disappeared(self._before(), self._after(top_failed=False)))

    def test_container_not_exited_rejects(self):
        self.assertFalse(descendants_disappeared(self._before(), self._after(container_exited=False)))

    def test_wrong_container_id_rejects(self):
        self.assertFalse(descendants_disappeared(self._before(), self._after(container_id='other')))

    def test_pid_list_mismatch_between_before_and_after_rejects(self):
        self.assertFalse(descendants_disappeared(self._before(), self._after(pids=[10])))

    def test_after_timestamp_before_before_finished_rejects(self):
        """Post observation must not predate the pre-termination observation."""
        self.assertFalse(descendants_disappeared(self._before(), self._after(monotonic=0.5)))

    def test_single_pid_before_rejects(self):
        """Must have at least 2 tracked PIDs to confirm parent+child."""
        self.assertFalse(descendants_disappeared(
            self._before(pids=[10], parents={10: 1}), self._after(pids=[10])))

    def test_no_parent_child_relationship_in_before_rejects(self):
        """Before record without any intra-PID parent-child link must be rejected."""
        # Both PIDs have init as parent — no relationship between them
        self.assertFalse(descendants_disappeared(
            self._before(parents={10: 1, 11: 1}), self._after()))

    def test_missing_mechanism_key_falls_through_to_wsl_format(self):
        """A before record without 'mechanism' is treated as WSL /proc format (legacy)."""
        before_wsl = {'namespace': 'docker-desktop:/proc', 'pids': [10, 11],
            'exit_code': 0, 'stdout': 'boot\n10 (p) S 1 a\n11 (p) S 10 a\n',
            'finished': 1.0,
            'docker_top': 'PID PPID COMMAND\n10 1 python\n11 10 python\n'}
        after_wsl = {'namespace': 'docker-desktop:/proc', 'pids': [10, 11],
            'exit_code': 0, 'stdout': 'boot\nABSENT:10\nABSENT:11\n', 'monotonic': 2.0}
        # This should evaluate via WSL path; with ABSENT in before it fails
        before_absent = dict(before_wsl, stdout='boot\nABSENT:10\nABSENT:11\n')
        self.assertFalse(descendants_disappeared(before_absent, after_wsl))


if __name__=='__main__':
    unittest.main()
