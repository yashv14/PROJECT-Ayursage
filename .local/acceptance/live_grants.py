from pathlib import Path
import sys,json,secrets,uuid,sqlite3,hashlib
from datetime import datetime,timedelta
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()))
from sqlalchemy.engine import URL
from backend.app import create_app
from backend.app.database import db
from backend.app.api.assessment_validation import CATEGORICAL_INPUTS,NUMERIC_INPUTS

target=Path('.local/auth/auth.sqlite3').resolve()
proof=json.loads(Path('.local/acceptance/backup-evidence.json').read_text())
assert str(target)==proof['source']
with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as con:
    assert con.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0005_patient_doctor_grants'
origin='http://localhost:5173'
run=uuid.uuid4().hex[:12]
password=secrets.token_urlsafe(32)
evidence={'origin':origin,'run':run,'browser_verified':False,'requests':[],'controlled_clock_checks':[]}
def request(path,method='GET',payload=None,token=None,expected=200):
    headers={'Accept':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    if payload is not None: headers['Content-Type']='application/json'
    req=Request(origin+path,method=method,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
    try: response=urlopen(req,timeout=10)
    except HTTPError as error: response=error
    with response:
        status=response.status; result=json.loads(response.read())
    evidence['requests'].append({'method':method,'path':path,'status':status})
    assert status==expected, (method,path,status,expected)
    return result

app=create_app({'SQLALCHEMY_DATABASE_URI':URL.create('sqlite',database=str(target)),
                'JWT_SECRET_KEY':Path('.local/auth/jwt.key').read_text().strip(), 'TESTING':True})
runner=app.test_cli_runner()
accounts={}
for actor in ('owner','other'):
    email=f'accept-{actor}-{run}@example.invalid'
    user=request('/api/auth/register','POST',{'email':email,'password':password},expected=201)['user']
    token=request('/api/auth/login','POST',{'email':email,'password':password})['access_token']
    assert request('/api/auth/me',token=token)['user']==user
    profile=request('/api/patients/me',token=token)['patient']
    assert profile['owner_user_id']==user['id']
    accounts[actor]={'user':user,'token':token,'profile':profile}
for actor,role in (('doctor','doctor'),('admin','admin')):
    email=f'accept-{actor}-{run}@example.invalid'
    result=runner.invoke(args=['create-privileged-user','--email',email,'--role',role],input=password+'\n'+password+'\n')
    assert result.exit_code==0, 'Synthetic staff provisioning failed'
    token=request('/api/auth/login','POST',{'email':email,'password':password})['access_token']
    user=request('/api/auth/me',token=token)['user']
    accounts[actor]={'user':user,'token':token}
owner=accounts['owner']; doctor=accounts['doctor']; admin=accounts['admin']; other=accounts['other']
patient_id=owner['profile']['id']; other_id=other['profile']['id']
base=f'/api/patients/{patient_id}'
grant_url=base+'/doctor-access-grants'
payload={'inputs':{**{name:'Synthetic acceptance fixture' for name in CATEGORICAL_INPUTS},
                   **dict(zip(NUMERIC_INPUTS,(120,80,72,65)))},'notes':'Synthetic grant acceptance only; no medical advice.'}
assessment=request(base+'/assessments','POST',payload,owner['token'],201)['assessment']
detail=base+f"/assessments/{assessment['id']}"
assert request(base+'/assessments',token=owner['token'])['assessments']==[assessment]
assert request(detail,token=owner['token'])['assessment']==assessment
request(base+'/assessments',token=doctor['token'],expected=403)
grant_body={'doctor_user_id':doctor['user']['id'],'consent_reference':f'synthetic-consent-{run}-1'}
request(grant_url,'POST',grant_body,admin['token'],403)
result=runner.invoke(args=['authorize-grant-administrator','--email',admin['user']['email']])
assert result.exit_code==0, 'Explicit synthetic grant administrator authorization failed'
Path(f'.local/acceptance/synthetic-consent-{run}.txt').write_text(
    f'SYNTHETIC ACCEPTANCE EVIDENCE ONLY\nPatient owner user {owner["user"]["id"]}, patient {patient_id}, doctor user {doctor["user"]["id"]}.\n'
    f'Administrator user {admin["user"]["id"]} attests to synthetic consent for assessment history/detail reads for 30 days.\n'
    f'References: synthetic-consent-{run}-1 and synthetic-consent-{run}-2.\nNo real person or patient data.\n')
request(grant_url,'POST',{'doctor_user_id':doctor['user']['id']},admin['token'],400)
grant=request(grant_url,'POST',grant_body,admin['token'],201)['grant']
issued=datetime.fromisoformat(grant['issued_at']); expiry=datetime.fromisoformat(grant['expires_at'])
assert expiry-issued==timedelta(days=30)
assert grant['issuer_user_id']==admin['user']['id'] and grant['consent_owner_user_id']==owner['user']['id']
with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as con:
    row=con.execute('SELECT issuer_user_id,consent_reference,issued_at,expires_at,status FROM patient_doctor_grants WHERE id=?',(grant['id'],)).fetchone()
    assert row[0]==admin['user']['id'] and row[1]==grant_body['consent_reference'] and row[4]=='issued'
    assert datetime.fromisoformat(row[3])-datetime.fromisoformat(row[2])==timedelta(days=30)
assert request(base+'/assessments',token=doctor['token'])['assessments']==[assessment]
assert request(detail,token=doctor['token'])['assessment']==assessment
request(f'/api/patients/{other_id}/assessments',token=doctor['token'],expected=403)
request(f'/api/patients/{other_id}/assessments/{assessment["id"]}',token=doctor['token'],expected=403)
request(base,token=doctor['token'],expected=403)
request('/api/patients/me',token=doctor['token'],expected=403)
request(base+'/assessments','POST',payload,doctor['token'],403)
request(base+'/assessments',token=admin['token'],expected=403)
request(detail+'/review','POST',{},doctor['token'],404)
request(grant_url,'POST',grant_body,owner['token'],403)
request(grant_url+f'/{grant["id"]}/revoke','POST',{},other['token'],404)
assert request(grant_url,token=owner['token'])['grants']==[grant]
with app.test_client() as client:
    for instant,expected in ((expiry.replace(tzinfo=None)-timedelta(seconds=1),200),
                             (expiry.replace(tzinfo=None),403)):
        with patch('backend.app.auth.grants.utc_now',return_value=instant):
            for path in (base+'/assessments',detail):
                response=client.get(path,headers={'Authorization':'Bearer '+doctor['token']})
                assert response.status_code==expected
                evidence['controlled_clock_checks'].append({'path':path,'grant_clock':instant.isoformat()+'Z','status':response.status_code})
assert request(detail,token=doctor['token'])['assessment']==assessment
revoked=request(grant_url+f'/{grant["id"]}/revoke','POST',{},owner['token'])['grant']
assert revoked['status']=='revoked' and revoked['revoked_by_user_id']==owner['user']['id']
request(base+'/assessments',token=doctor['token'],expected=403)
request(detail,token=doctor['token'],expected=403)
grant_body['consent_reference']=f'synthetic-consent-{run}-2'
second=request(grant_url,'POST',grant_body,admin['token'],201)['grant']
request(detail,token=doctor['token'])
request(grant_url+f'/{second["id"]}/revoke','POST',{},admin['token'])
request(detail,token=doctor['token'],expected=403)
request(detail,token=owner['token'])
request('/api/auth/me',expected=401)
request('/api/auth/login','POST',{'email':owner['user']['email'],'password':'incorrect-password'},expected=401)
fresh=request('/api/auth/login','POST',{'email':owner['user']['email'],'password':password})['access_token']
assert request(detail,token=fresh)['assessment']==assessment
with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as con:
    assert con.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
    assert con.execute('PRAGMA foreign_key_check').fetchall()==[]
    for t in proof['counts']:
        # Original row IDs and complete contents still match the verified backup.
        with sqlite3.connect(Path(proof['backup']).as_uri()+'?mode=ro',uri=True) as backup:
            original=backup.execute('SELECT * FROM '+t+' ORDER BY id').fetchall()
        rows=[con.execute('SELECT * FROM '+t+' WHERE id=?',(row[0],)).fetchone() for row in original]
        assert rows==original, 'Original records changed'
    persisted=con.execute('SELECT id,status,revoked_by_user_id,revoked_at FROM patient_doctor_grants WHERE id IN (?,?) ORDER BY id',(grant['id'],second['id'])).fetchall()
    assert len(persisted)==2 and all(row[1]=='revoked' and row[3] for row in persisted)
    counts={t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in (*proof['counts'],'patient_doctor_grants','grant_administrators')}
evidence.update({'result':'PASS','target':str(target),'revision':'0005_patient_doctor_grants',
 'synthetic_user_ids':{actor:data['user']['id'] for actor,data in accounts.items()},
 'synthetic_patient_ids':[patient_id,other_id],'assessment_id':assessment['id'],
 'grant_ids':[grant['id'],second['id']],'grant_duration_seconds':int((expiry-issued).total_seconds()),
 'persisted_revocations':persisted,'final_counts':counts,'original_records_unchanged':True,
 'cleanup':'Both grants revoked via supported endpoints. Rows retained: no safe application deletion endpoint; audit history intentionally preserved.'})
Path('.local/acceptance/live-evidence.json').write_text(json.dumps(evidence,indent=2))
with app.app_context(): db.session.remove(); db.engine.dispose()
print(json.dumps(evidence,indent=2))
