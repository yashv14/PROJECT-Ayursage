from pathlib import Path
import sys,json,uuid,secrets,sqlite3
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote
sys.path.insert(0,str(Path.cwd()))
from backend.app import create_app
from backend.app.database import db
from backend.app.api.assessment_validation import CATEGORICAL_INPUTS,NUMERIC_INPUTS
target=(Path.cwd()/'.local/auth/auth.sqlite3').resolve()
app=create_app({'SQLALCHEMY_DATABASE_URI':'sqlite:///'+target.as_posix(), 'JWT_SECRET_KEY':Path('.local/auth/jwt.key').read_text().strip(),'TESTING':True})
runner=app.test_cli_runner();run=uuid.uuid4().hex[:10];password=secrets.token_urlsafe(32)
origin='http://127.0.0.1:5173'
proof={'origin':origin,'run':run,'browser_verified':False,'requests':[]}
def request(path,method='GET',payload=None,token=None,expected=200):
    headers={'Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    if payload is not None:headers['Content-Type']='application/json'
    req=Request(origin+path,method=method,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
    try:r=urlopen(req,timeout=10)
    except HTTPError as error:r=error
    with r:
        status=r.status;data=json.loads(r.read())
    proof['requests'].append({'method':method,'path':path.split('?')[0],'status':status})
    assert status==expected,(path,status,expected)
    return data
accounts={}
for actor,role in (('owner','patient'),('other','patient'),('doctor','doctor'),('doctor2','doctor'),('reception','receptionist'),('reception2','receptionist')):
    email=f'reception-{actor}-{run}@example.invalid'
    if role=='patient':request('/api/auth/register','POST',{'email':email,'password':password},expected=201)
    else:
        result=runner.invoke(args=['create-privileged-user','--email',email,'--role',role],input=password+'\n'+password+'\n')
        assert result.exit_code==0,'Synthetic staff provisioning failed'
    token=request('/api/auth/login','POST',{'email':email,'password':password})['access_token']
    user=request('/api/auth/me',token=token)['user'];accounts[actor]={'token':token,'user':user}
    if role=='patient':accounts[actor]['profile']=request('/api/patients/me',token=token)['patient']
rec=accounts['reception']['token'];rec2=accounts['reception2']['token'];owner=accounts['owner'];doc=accounts['doctor'];doc2=accounts['doctor2']
lookup=request('/api/reception/patients?email='+quote(owner['user']['email']),token=rec)['patient']
assert set(lookup)=={'id','email','administrative_status'} and lookup['id']==owner['profile']['id']
request('/api/reception/patients?email=not-a-match@example.invalid',token=rec,expected=404)
request('/api/reception/doctors',token=rec)
body={'patient_id':lookup['id'],'doctor_user_id':doc['user']['id'],'starts_at':'2026-12-01T10:00:00+05:30'}
row=request('/api/reception/appointments','POST',body,rec,201)['appointment'];id=row['id']
assert row['starts_at']=='2026-12-01T04:30:00Z' and row['ends_at']=='2026-12-01T05:00:00Z'
request('/api/reception/appointments','POST',{**body,'patient_id':accounts['other']['profile']['id']},rec,409)
request('/api/reception/appointments','POST',{**body,'doctor_user_id':doc2['user']['id']},rec,409)
request('/api/reception/appointments',token=owner['token'],expected=403)
request('/api/reception/appointments',token=doc['token'],expected=403)
path=f'/api/reception/appointments/{id}'
request(path+'/reschedule','POST',{'starts_at':'2026-12-02T10:00:00+05:30'},rec2)
request(path+'/status','POST',{'status':'checked_in'},rec2)
request(path+'/reschedule','POST',{'starts_at':'2026-12-03T10:00:00Z'},rec,409)
request(path+'/status','POST',{'status':'cancelled'},rec,409)
request(path+'/status','POST',{'status':'completed'},rec)
request(path+'/status','POST',{'status':'scheduled'},rec,409)
others=[]
for date,terminal in (('2026-12-03T10:00:00Z','cancelled'),('2026-12-04T10:00:00Z','no_show')):
    another=request('/api/reception/appointments','POST',{**body,'starts_at':date},rec,201)['appointment']
    request(f'/api/reception/appointments/{another["id"]}/status','POST',{'status':terminal},rec2);others.append(another['id'])
request('/api/reception/appointments',token=rec2)
patient_path=f'/api/patients/{lookup["id"]}'
assessment_payload={'inputs':{**{name:'Synthetic receptionist regression' for name in CATEGORICAL_INPUTS},**dict(zip(NUMERIC_INPUTS,(120,80,72,65)))}}
assessment=request(patient_path+'/assessments','POST',assessment_payload,owner['token'],201)['assessment']
detail=patient_path+f'/assessments/{assessment["id"]}'
request(patient_path+'/assessments',token=owner['token']);request(detail,token=owner['token'])
for method,payload,path in (('GET',None,patient_path),('GET',None,patient_path+'/assessments'),('GET',None,detail),('POST',assessment_payload,patient_path+'/assessments'),('GET',None,patient_path+'/doctor-access-grants'),('POST',{},patient_path+'/doctor-access-grants'),('POST',{},patient_path+'/doctor-access-grants/1/revoke')):
    request(path,method,payload,rec,403)
request(detail+'/review','POST',{},rec,404)
request(patient_path+'/assessments',token=doc['token'],expected=403)
request('/api/reception/appointments',expected=401)
backup_proof=json.loads(Path('.local/reception/backup-evidence.json').read_text())
with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as con,sqlite3.connect(Path(backup_proof['backup']).as_uri()+'?mode=ro',uri=True) as backup:
    assert con.execute('PRAGMA integrity_check').fetchall()==[('ok',)] and con.execute('PRAGMA foreign_key_check').fetchall()==[]
    for table in backup_proof['before']:
        if table=='alembic_version':continue
        original=backup.execute('SELECT * FROM "'+table+'" ORDER BY 1').fetchall()
        key='user_id' if table=='grant_administrators' else 'id'
        assert original==[con.execute('SELECT * FROM "'+table+'" WHERE '+key+'=?',(old[0],)).fetchone() for old in original],table
    events=con.execute('SELECT COUNT(*) FROM appointment_events WHERE appointment_id IN (?,?,?)',(id,*others)).fetchone()[0]
    assert events==8
    statuses=con.execute('SELECT id,status FROM appointments WHERE id IN (?,?,?) ORDER BY id',(id,*others)).fetchall()
    assert [row[1] for row in statuses]==['completed','cancelled','no_show']
proof.update({'result':'PASS','revision':'0006_receptionist_appointments','synthetic_user_ids':{actor:data['user']['id'] for actor,data in accounts.items()},'appointment_statuses':statuses,'event_count':events,'assessment_id':assessment['id'],'original_rows_unchanged':True,'cleanup':'Synthetic rows retained; appointments ended through supported terminal transitions. No deletion endpoint.'})
Path('.local/reception/live-evidence.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))
with app.app_context():db.session.remove();db.engine.dispose()
