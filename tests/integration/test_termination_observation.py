"""Synthetic evidence validation, not a provisioned process-exit observer."""

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'infra/docker'))
from worker_diagnostics import classify_tracked_termination, matching_alive
from worker_diagnostic_audit import observe_container_exit
import test_worker_diagnostics as diagnostics
import test_worker_watchdog as existing


class ObservationTests(unittest.TestCase):
    def before(self): return diagnostics.DiagnosticEvidenceTests().snapshot()
    def exits(self):
        before=self.before()
        return {'outcome':'ok','observer_validated':True,'survives_worker_exit':True,
            'boot_id':before['boot_id'],'target_pid_namespace':'pid:[123]',
            'processes':[dict(p,terminated=True) for p in before['processes']]}

    def test_valid_precondition_has_both_processes_alive(self):
        self.assertTrue(matching_alive(self.before(),self.before()))

    def test_simulated_observer_reports_both_tracked_exits(self):
        result=classify_tracked_termination(self.before(),self.exits(),container_exited=True)
        self.assertTrue(result['parent_termination_verified'])
        self.assertTrue(result['child_termination_verified'])
        self.assertTrue(result['accepted'])

    def test_wrong_namespace_and_boot_are_rejected(self):
        for key,value in [('target_pid_namespace','pid:[wrong]'),('boot_id','wrong')]:
            observation=self.exits(); observation[key]=value
            result=classify_tracked_termination(self.before(),observation,container_exited=True)
            self.assertFalse(result['accepted']); self.assertTrue(result['recovery_required'])

    def test_pid_reuse_or_identity_mismatch_is_rejected(self):
        for key,value in [('start_ticks',999),('pid',42),('ppid',2),('pid_namespace','wrong')]:
            observation=self.exits(); observation['processes'][1][key]=value
            result=classify_tracked_termination(self.before(),observation,container_exited=True)
            self.assertEqual(result['reason'],'identity_mismatch'); self.assertFalse(result['accepted'])

    def test_observer_failure_and_timeout_are_explicit(self):
        for outcome in ('unavailable','timeout'):
            observation=self.exits(); observation['outcome']=outcome
            result=classify_tracked_termination(self.before(),observation,container_exited=True)
            self.assertEqual(result['reason'],'observer_'+outcome)
            self.assertFalse(result['parent_termination_verified'])

    def test_unvalidated_or_non_surviving_observer_cannot_pass(self):
        for key in ('observer_validated','survives_worker_exit'):
            observation=self.exits(); observation[key]=False
            self.assertFalse(classify_tracked_termination(self.before(),observation,container_exited=True)['accepted'])

    def test_container_exit_without_descendants_remains_unaccepted(self):
        result=classify_tracked_termination(self.before(),{},container_exited=True)
        self.assertTrue(result['container_exited']); self.assertFalse(result['accepted'])
        report=existing.CompletionTests().valid(); report.update(result)
        self.assertFalse(existing.scenario_passed(report))

    def test_only_one_tracked_exit_is_insufficient(self):
        observation=self.exits(); observation['processes'][1]['terminated']=False
        result=classify_tracked_termination(self.before(),observation,container_exited=True)
        self.assertTrue(result['parent_termination_verified'])
        self.assertFalse(result['child_termination_verified']); self.assertFalse(result['accepted'])

    def test_container_wait_and_inspect_never_issue_post_stop_exec(self):
        config={'State':{'Running':False,'Status':'exited','ExitCode':137}}
        with patch('worker_diagnostic_audit.command',return_value={'exit_code':0,'stdout':'137\n'}) as command, \
                patch('worker_diagnostic_audit.inspect_owned',return_value=config):
            _,result=observe_container_exit(Path('unused'),'exact-id','name')
        self.assertEqual(command.call_args.args[2],['docker','wait','exact-id'])
        self.assertTrue(result['container_exited'])
        self.assertFalse(result['parent_termination_verified']); self.assertFalse(result['accepted'])

    def test_failed_wait_is_not_container_confirmation(self):
        config={'State':{'Running':False,'Status':'exited','ExitCode':137}}
        with patch('worker_diagnostic_audit.command',return_value={'outcome':'unavailable'}), \
                patch('worker_diagnostic_audit.inspect_owned',return_value=config):
            _,result=observe_container_exit(Path('unused'),'exact-id','name')
        self.assertFalse(result['container_exited']); self.assertTrue(result['recovery_required'])


if __name__=='__main__': unittest.main()
