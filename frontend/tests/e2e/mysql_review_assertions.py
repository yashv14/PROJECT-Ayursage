"""Real disposable-MySQL review/migration/concurrency checks; no inference."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, Lock, get_ident
from time import monotonic

from sqlalchemy import event, select, text

from backend.app.database import db
from backend.app.models import AssessmentReview, User
from backend.app.models.review import ReviewHistoryImmutable
from backend.app.auth.routes import create_account
from backend.app.auth.security import issue_token
from backend.app.auth.grants import utc_now
from backend.app.api.assessment_validation import INPUT_FEATURES, NUMERIC_INPUTS, OUTPUT_TARGETS


def prepare_baseline(connection):
    """Synthetic legacy records using the actual 0006 schema, before 0007."""
    ids=[]
    for role, name in ((1,'patient'),(2,'doctor'),(3,'admin')):
        result=connection.execute(text('INSERT INTO users (email, role_id, password_hash) VALUES (:email,:role,NULL)'),
            {'email':'baseline-review-'+name+'@example.invalid','role':role})
        ids.append(result.lastrowid)
    patient=connection.execute(text('INSERT INTO patients (owner_user_id) VALUES (:owner)'),{'owner':ids[0]}).lastrowid
    assessment=connection.execute(text('INSERT INTO clinical_assessments (patient_id, recorded_by_user_id, notes) VALUES (:patient,:owner,:notes)'),
        {'patient':patient,'owner':ids[0],'notes':'SYNTHETIC legacy assessment'}).lastrowid
    connection.execute(text("INSERT INTO assessment_reviews (assessment_id, sequence, actor_user_id, from_state, to_state, reason) VALUES (:assessment,1,:doctor,'pending_review','returned_for_changes',:reason)"),
        {'assessment':assessment,'doctor':ids[1],'reason':'SYNTHETIC legacy history, not a newly authorized decision'})
    now=utc_now()
    connection.execute(text("INSERT INTO patient_doctor_grants (patient_id,doctor_user_id,consent_owner_user_id,consent_reference,issuer_user_id,scope,status,issued_at,expires_at,active_slot) VALUES (:patient,:doctor,:owner,'synthetic-baseline',:admin,'assessment_read','issued',:issued,:expires,1)"),
        {'patient':patient,'doctor':ids[1],'owner':ids[0],'admin':ids[2],'issued':now,'expires':now+timedelta(days=30)})
    return assessment


def verify_baseline(connection, assessment):
    row=connection.execute(text('SELECT allow_review FROM patient_doctor_grants WHERE consent_reference=\'synthetic-baseline\'')).scalar_one()
    assert row==0, 'Legacy read grant was escalated by migration'
    row=connection.execute(text('SELECT sequence,from_state,to_state,reason,recommendations,prescriptions FROM assessment_reviews WHERE assessment_id=:id'),{'id':assessment}).one()
    assert tuple(row)==(1,'pending_review','returned_for_changes','SYNTHETIC legacy history, not a newly authorized decision',None,None)


def payload(version=0, decision='returned_for_changes', note='SYNTHETIC race'):
    return {'expected_version':version,'decision':decision,'clinical_notes':note,
        'recommendations':{name:'SYNTHETIC human recommendation' for name in OUTPUT_TARGETS},
        'prescriptions':[{'medication':'SYNTHETIC medicine','dose':'manual dose','route':'manual route',
            'frequency':'manual frequency','duration':'manual duration','instructions':'manual instructions'}]}


def verify_mysql_reviews(app):
    with app.app_context():
        assert db.engine.dialect.name=='mysql'
        engine=db.engine
        owner=create_account('mysql-review-patient@example.invalid','fixture-password-123','patient')
        doctor=create_account('mysql-review-doctor@example.invalid','fixture-password-123','doctor')
        admin=db.session.scalar(select(User).where(User.email=='admin@example.invalid'))
        patient_id,doctor_id=owner.patient.id,doctor.id
        headers={name:{'Authorization':'Bearer '+issue_token(user)} for name,user in [('owner',owner),('doctor',doctor),('admin',admin)]}
    client=app.test_client()
    base=f'/api/patients/{patient_id}/assessments'
    grants=f'/api/patients/{patient_id}/doctor-access-grants'
    response=client.post(grants,json={'doctor_user_id':doctor_id,'consent_reference':'synthetic-mysql-review','allow_review':True},headers=headers['admin'])
    assert response.status_code==201
    grant=response.get_json()['grant']
    races=[]
    for trial in range(3):
        response=client.post(base,json={'inputs':{name:0 if name in NUMERIC_INPUTS else 'Synthetic MySQL review' for name in INPUT_FEATURES},'predict':False},headers=headers['owner'])
        assert response.status_code==201
        assessment_id=response.get_json()['assessment']['id']
        url=f'{base}/{assessment_id}/reviews'
        both_entered=Event(); mutex=Lock(); lock_requests={}
        def observe(connection,cursor,statement,parameters,context,many):
            if 'FOR UPDATE' in statement and 'patient_doctor_grants' in statement:
                with mutex:
                    lock_requests[get_ident()]={'connection_id':connection.connection.driver_connection.thread_id(),'at':monotonic()}
                    if len(lock_requests)==2: both_entered.set()
        event.listen(engine,'before_cursor_execute',observe)
        blocker=engine.connect(); transaction=blocker.begin()
        blocker.execute(text('SELECT id FROM clinical_assessments WHERE id=:id FOR UPDATE'),{'id':assessment_id})
        def submit(label):
            with app.test_client() as concurrent_client:
                r=concurrent_client.post(url,json=payload(note='SYNTHETIC race '+label),headers=headers['doctor'])
                return r.status_code,r.get_json()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(submit,label) for label in ('A','B')]
                overlap=both_entered.wait(5)
                transaction.rollback()
                results=[future.result(timeout=10) for future in futures]
            assert overlap, 'Two independent review lock requests were not observed'
        finally:
            if transaction.is_active: transaction.rollback()
            blocker.close(); event.remove(engine,'before_cursor_execute',observe)
        assert len({value['connection_id'] for value in lock_requests.values()})==2
        assert sorted(status for status,_ in results)==[201,409], results
        winner=next(data for status,data in results if status==201)
        persisted=client.get(url,headers=headers['doctor']).get_json()
        assert persisted==winner and persisted['version']==1
        original=persisted['reviews'][0]
        assert original['actor_user_id']==doctor_id and original['decided_at'].endswith('Z')
        assert client.post(url,json=payload(),headers=headers['doctor']).status_code==409
        for version,decision in ((1,'pending_review'),(2,'approved')):
            r=client.post(url,json=payload(version,decision,'SYNTHETIC revision '+str(version)),headers=headers['doctor'])
            assert r.status_code==201, r.status_code
        history=client.get(url,headers=headers['doctor']).get_json()
        assert history['version']==3 and history['reviews'][0]==original
        assert [r['sequence'] for r in history['reviews']]==[1,2,3]
        assert client.post(url,json=payload(3,'pending_review'),headers=headers['doctor']).status_code==409
        with app.app_context():
            row=db.session.scalar(select(AssessmentReview).where(AssessmentReview.assessment_id==assessment_id,AssessmentReview.sequence==1))
            row.reason='forbidden replacement'
            try:
                db.session.commit()
                raise AssertionError('Immutable review was edited')
            except ReviewHistoryImmutable:
                db.session.rollback()
        races.append({'trial':trial+1,'assessment_id':assessment_id,'statuses':[status for status,_ in results],
            'distinct_connections':len(lock_requests),'overlap_observed':overlap,'version':history['version']})
    assert client.post(grants+f"/{grant['id']}/revoke",json={},headers=headers['owner']).status_code==200
    assert client.post(url,json=payload(3),headers=headers['doctor']).status_code==403
    assert client.get(url,headers=headers['doctor']).status_code==403
    return {'checks':['0006_data_preserved_through_0007','concurrent_version_conflicts','persisted_reload',
        'append_only_history','actor_utc_timestamps','terminal_version_conflicts','revoked_review_denied'],'races':races}
