"""Diagnostic regressions with harmless fixtures; no Docker or ML execution."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'infra/docker'))
import worker_diagnostics
from worker_diagnostics import EvidenceLog, Heartbeat, HeartbeatError, matching_alive, bounded_evidence_write
from worker_watchdog import monitor, scenario_passed
import test_worker_watchdog as existing
Clock, Worker = existing.Clock, existing.Worker


class Records:
    def __init__(self): self.records=[]
    def record(self,event): self.records.append(event)


class HeartbeatTests(unittest.TestCase):
    def fixture(self,directory):
        clock=Clock(); clock.now=10
        records=Records()
        heartbeat=Heartbeat(Path(directory)/'heartbeat.json',
            {'token':'run','scenario':'timeout','start':0},records,clock=clock)
        return heartbeat,clock,records

    def test_fresh_write_read_records_exact_values_and_clock(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.write(); clock.now=11
            self.assertEqual(hb.read(),10)
            write,read=records.records
            self.assertEqual(write['value'],read['value'])
            self.assertEqual(read['age'],1); self.assertFalse(read['recovery_decision'])
            self.assertEqual(write['before'],10); self.assertEqual(write['after'],10)
            self.assertEqual(read['before'],11); self.assertEqual(read['after'],11)
            self.assertEqual(write['identity']['clock_domain'],read['identity']['clock_domain'])

    def test_stale_value_records_recovery_age(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.write(); clock.now=13
            hb.read(); event=records.records[-1]
            self.assertEqual(event['age'],3); self.assertTrue(event['recovery_decision'])
            self.assertEqual(event['reason'],'supervisor_unresponsive')

    def test_invalid_json_missing_and_read_error_are_explicit(self):
        for mode,exception in [('invalid','JSONDecodeError'),('missing','FileNotFoundError'),('read-error','PermissionError')]:
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                hb,clock,records=self.fixture(directory)
                if mode=='invalid': hb.path.write_text('{')
                if mode=='read-error':
                    with patch.object(worker_diagnostics,'read_published_text',side_effect=PermissionError()):
                        with self.assertRaises(HeartbeatError): hb.read()
                else:
                    with self.assertRaises(HeartbeatError): hb.read()
                event=records.records[-1]
                self.assertEqual(event['exception_type'],exception)
                self.assertEqual(event['outcome'],'error'); self.assertIsNone(event['age'])
                self.assertTrue(event['recovery_decision'])

    def test_inconsistent_timestamps_and_domain_are_rejected(self):
        for field,value in [('monotonic',20),('monotonic',-1),('monotonic',True),
                ('run_id','wrong'),('format','unknown'),('clock_domain','unrelated')]:
            with self.subTest(field=field), TemporaryDirectory() as directory:
                hb,clock,records=self.fixture(directory); hb.write()
                data=json.loads(hb.path.read_text())
                if field=='clock_domain': data['writer'][field]=value
                else: data[field]=value
                hb.path.write_text(json.dumps(data))
                with self.assertRaises(HeartbeatError): hb.read()
                self.assertEqual(records.records[-1]['exception_type'],'ValueError')

    def test_timestamp_regression_is_rejected(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory); hb.write(); hb.read()
            data=json.loads(hb.path.read_text()); data['monotonic']=9
            hb.path.write_text(json.dumps(data))
            with self.assertRaises(HeartbeatError): hb.read()

    def test_read_failure_monitor_requests_kill_without_start_time_substitution(self):
        clock=Clock(); worker=Worker(clock)
        def unavailable(): raise HeartbeatError('read failed')
        result=monitor(worker,0,5,3,unavailable,lambda:None,clock=clock,sleep=clock.sleep)
        self.assertTrue(worker.killed)
        self.assertEqual(result['reason'],'heartbeat_observation_unavailable')
        self.assertFalse(result['accepted'])
        self.assertTrue(result['recovery_required'])
        report=existing.CompletionTests().valid(); report.update(result)
        self.assertFalse(scenario_passed(report))

    def test_write_error_is_recorded(self):
        with TemporaryDirectory() as directory:
            hb,clock,records=self.fixture(directory)
            with patch.object(Path,'write_text',side_effect=PermissionError()):
                with self.assertRaises(HeartbeatError): hb.write()
            self.assertEqual(records.records[-1]['exception_type'],'PermissionError')


class DiagnosticEvidenceTests(unittest.TestCase):
    def test_raw_evidence_publication_wait_is_bounded_and_failure_explicit(self):
        gate=Event()
        self.assertFalse(bounded_evidence_write(lambda:gate.wait(),timeout=0.01))
        gate.set()
        self.assertTrue(bounded_evidence_write(lambda:None))
        def fail(): raise PermissionError()
        self.assertFalse(bounded_evidence_write(fail))

    def test_record_limit_is_fail_closed(self):
        with TemporaryDirectory() as directory:
            log=EvidenceLog(Path(directory)/'log.jsonl',limit=1)
            log.record({'event':'one'}); log.record({'event':'two'})
            self.assertFalse(log.finish())

    def test_stalled_writer_does_not_block_finish(self):
        gate=Event()
        log=EvidenceLog(Path('unused'),writer=lambda line:gate.wait())
        log.record({'event':'one'})
        self.assertFalse(log.finish(timeout=0.01))
        gate.set(); log.thread.join(1)

    def test_logging_error_sets_evidence_incomplete(self):
        def fail(line): raise PermissionError()
        log=EvidenceLog(Path('unused'),writer=fail); log.record({'event':'one'})
        self.assertFalse(log.finish())

    def snapshot(self):
        return {'boot_id':'boot','observer':{'pid_namespace':'pid:[123]'},'processes':[
            {'pid':1,'ppid':0,'start_ticks':100,'pid_namespace':'pid:[123]','state':'S'},
            {'pid':7,'ppid':1,'start_ticks':101,'pid_namespace':'pid:[123]','state':'S'}]}

    def test_same_process_identities_and_relationship_are_alive(self):
        self.assertTrue(matching_alive(self.snapshot(),self.snapshot()))

    def test_pid_reuse_namespace_change_absence_and_zombie_fail(self):
        for key,value in [('start_ticks',999),('pid_namespace','pid:[other]'),('ppid',2),('state','Z')]:
            observation=self.snapshot(); observation['processes'][1][key]=value
            self.assertFalse(matching_alive(self.snapshot(),observation))
        self.assertFalse(matching_alive(self.snapshot(),{}))

    def test_incomplete_logging_cannot_pass_acceptance(self):
        report=existing.CompletionTests().valid(); report['diagnostics_complete']=False
        self.assertFalse(scenario_passed(report))


if __name__=='__main__': unittest.main()
