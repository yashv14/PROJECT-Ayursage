"""One controlled harmless worker. Diagnostic results never accept Step 1.3."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from worker_control_audit import ROOT, create_worker, IMAGE
from worker_watchdog import publish
from worker_diagnostics import EvidenceLog, Heartbeat, host_identity, matching_alive, bounded_evidence_write

INCOMPLETE_EVIDENCE = set()


def command(directory, label, args, timeout=2):
    before = time.monotonic()
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        evidence = {'command':args, 'before':before, 'after':time.monotonic(),
            'identity':host_identity(), 'exit_code':result.returncode,
            'stdout':result.stdout, 'stderr':result.stderr, 'outcome':'returned'}
    except (OSError,subprocess.TimeoutExpired) as error:
        evidence = {'command':args,'before':before,'after':time.monotonic(),
            'identity':host_identity(), 'outcome':'unavailable','exception_type':type(error).__name__}
    if not bounded_evidence_write(lambda:publish(directory/(label+'.json'), evidence)):
        INCOMPLETE_EVIDENCE.add(str(directory))
        evidence['evidence_incomplete'] = True
    return evidence


def inspect_owned(directory, cid, name, label):
    result = command(directory,label,['docker','inspect',cid])
    config = json.loads(result['stdout'])[0]
    labels = config['Config'].get('Labels') or {}
    if (config['Id'] != cid or labels.get('ayursage.audit-name') != name
            or labels.get('ayursage.harmless-audit') != 'true'):
        raise RuntimeError('OWNERSHIP_MISMATCH')
    return config


def observe_container_exit(directory, cid, name):
    """Supported container-level observations; no descendant claim or post-stop exec."""
    waited=command(directory,'container-wait',['docker','wait',cid])
    config=inspect_owned(directory,cid,name,'config-after-kill')
    state=config['State']
    confirmed=(waited.get('exit_code')==0 and state['Running'] is False
        and state['Status']=='exited' and waited.get('stdout','').strip()==str(state['ExitCode']))
    return config, {'container_exited':confirmed, 'worker_exit':state['ExitCode'],
        'parent_termination_verified':False,'child_termination_verified':False,
        'post_observation':'container_level_only', 'accepted':False,'recovery_required':True,
        'reason':'DESCENDANT_OBSERVER_NOT_VALIDATED'}


def writer(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    log=EvidenceLog(directory/'heartbeat-writer.jsonl')
    heartbeat=Heartbeat(directory/'heartbeat.json',manifest,log)
    try:
        while not (directory/'writer-stop.json').exists() and time.monotonic()<manifest['deadline']:
            heartbeat.write()
            time.sleep(0.1)
    finally:
        publish(directory/'heartbeat-writer-status.json',{'complete':log.finish()})


def run():
    directory=ROOT/'reports'/('worker-diagnostic-'+uuid4().hex[:12])
    directory.mkdir(parents=True)
    (directory/'fixture.txt').write_text('harmless readonly fixture\n',newline='')
    start=time.monotonic()
    manifest={'token':uuid4().hex,'scenario':'controlled-diagnostic',
        'name':'ayursage-controls-diagnostic-'+uuid4().hex[:12],
        'start':start,'deadline':start+35,'image':IMAGE}
    publish(directory/'manifest.json',manifest)
    log=EvidenceLog(directory/'heartbeat-reader.jsonl')
    heartbeat=Heartbeat(directory/'heartbeat.json',manifest,log)
    with (directory/'writer-stdout.log').open('w') as out, (directory/'writer-stderr.log').open('w') as err:
        publisher=subprocess.Popen([sys._base_executable,'-B',__file__,'writer',str(directory)],
            stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    publish(directory/'writer-launch.json',{'pid':publisher.pid,'parent_pid':os.getpid()})
    cid=None
    report={'accepted':False,'step_1_3_accepted':False,'recovery_required':True,
        'parent_termination_verified':False,'child_termination_verified':False,
        'termination_requested':False,'container_exited':False,'precondition_alive':False}
    try:
        before=time.monotonic()
        cid=create_worker('timeout',manifest['name'],directory/'fixture.txt',command_timeout=10)
        publish(directory/'creation.json',{'before':before,'after':time.monotonic(),'id':cid})
        inspect_owned(directory,cid,manifest['name'],'config-before-start')
        command(directory,'start',['docker','start',cid])
        initial=None
        for i in range(10):
            observed=command(directory,'initial-observation-'+str(i),
                ['docker','exec',cid,'python','-I','-B','/probe.py','observe'])
            if observed.get('exit_code')==0:
                initial=json.loads(observed['stdout']); break
            time.sleep(0.1)
        if initial is None:
            raise RuntimeError('PRECONDITION_OBSERVATION_UNAVAILABLE')
        top=command(directory,'docker-top',['docker','top',cid,'-eo','pid,ppid,args'])
        pids=[int(row.split()[0]) for row in top['stdout'].splitlines()[1:]]
        script=('cat /proc/sys/kernel/random/boot_id; '
            'readlink /proc/self/ns/pid; readlink /proc/self/ns/mnt; readlink /proc/1/ns/pid; ')
        for pid in pids:
            script+=f'if test -d /proc/{pid}; then cat /proc/{pid}/stat /proc/{pid}/status; readlink /proc/{pid}/ns/pid; else echo ABSENT:{pid}; fi; '
        command(directory,'wsl-observation',['wsl','-d','docker-desktop','--exec','sh','-c',script])
        # Read actual publisher values in this host clock domain; never translate Linux clocks.
        while time.monotonic()<start+15:
            heartbeat.read()
            time.sleep(0.1)
        inspect_owned(directory,cid,manifest['name'],'config-before-kill')
        fresh=command(directory,'fresh-precondition',['docker','exec',cid,'python','-I','-B','/probe.py','observe'])
        alive=fresh.get('exit_code')==0 and matching_alive(initial,json.loads(fresh['stdout']))
        report['precondition_alive']=alive
        if not alive or time.monotonic()-fresh['after']>1:
            raise RuntimeError('PRECONDITION_FAILED_OR_STALE')
        report['termination_requested']=True
        kill=command(directory,'kill',['docker','kill','--signal','KILL',cid])
        report['termination_operation_succeeded']=kill.get('exit_code')==0
        config,container_result=observe_container_exit(directory,cid,manifest['name'])
        report.update(container_result)
        # Capture beyond FinishedAt; die event delivery can follow that state timestamp.
        until=(datetime.now(timezone.utc)+timedelta(seconds=0.5)).isoformat()
        command(directory,'events',['docker','events','--since',config['State']['StartedAt'],
            '--until',until,'--filter','container='+cid,'--format','{{json .}}'])
        command(directory,'worker-logs',['docker','logs','--timestamps',cid])
    except Exception as error:
        report.update(reason=type(error).__name__,error=str(error))
    finally:
        if cid is not None and not report['container_exited']:
            # Safety cleanup is distinct from a termination assertion; no deletion.
            config=inspect_owned(directory,cid,manifest['name'],'safety-inspection')
            if config['State']['Running']:
                command(directory,'safety-kill',['docker','kill','--signal','KILL',cid])
            inspect_owned(directory,cid,manifest['name'],'safety-final-state')
        publish(directory/'writer-stop.json',{'monotonic':time.monotonic()})
        try:
            publisher.wait(timeout=2)
        except subprocess.TimeoutExpired:
            publisher.terminate(); publisher.wait(timeout=2)
        writer_complete=(directory/'heartbeat-writer-status.json').exists() and json.loads((directory/'heartbeat-writer-status.json').read_text())['complete'] is True
        report['diagnostics_complete']=log.finish() and writer_complete and publisher.returncode==0
    report['diagnostics_complete'] &= str(directory) not in INCOMPLETE_EVIDENCE
    report.update(terminal_state='FINAL',elapsed_seconds=time.monotonic()-start,
        deadline_met=time.monotonic()<=manifest['deadline'],model_access=False,containers_retained=True)
    publish(directory/'result.json',report)
    raw=(directory/'result.json').read_bytes()
    publish(directory/'completion.json',{'result_sha256':hashlib.sha256(raw).hexdigest(),
        'monotonic':time.monotonic(),'identity':host_identity(),'publisher_exit':publisher.returncode,
        'diagnostic_only':True})
    print(json.dumps({'output':str(directory),'result':report},indent=2))
    return 1  # Inconclusive required post-observation cannot pass.


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='writer':
        writer(Path(sys.argv[2]))
    else:
        raise SystemExit(run())
