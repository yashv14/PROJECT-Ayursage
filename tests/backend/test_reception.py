"""Real administrative API, migration and concurrent SQLite booking regressions."""
import tempfile, threading, unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, create_engine
from backend.app import create_app
from backend.app.database import db, enable_sqlite_foreign_keys
from backend.app.models import User, Appointment, AppointmentEvent
from backend.app.auth.security import issue_token
from test_database import migration_config
import test_patients as patient_tests

class ReceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): patient_tests.PatientApiTests.setUpClass.__func__(cls)
    def setUp(self):
        patient_tests.PatientApiTests.setUp(self)
        for actor in ('receptionist','second_receptionist'):
            user=User(email=actor+'@example.invalid',role_id=4,password_hash=self.password_hash)
            db.session.add(user);db.session.flush();self.users[actor]=user
            self.headers[actor]={'Authorization':'Bearer '+issue_token(user)}
        user=User(email='doctor2@example.invalid',role_id=2,password_hash=self.password_hash)
        db.session.add(user);db.session.flush();self.users['doctor2']=user
        db.session.commit()
        self.body={'patient_id':self.patient.id,'doctor_user_id':self.users['doctor'].id,'starts_at':'2026-11-01T10:00:00+05:30'}
    def create(self,actor='receptionist',**changes):
        return self.client.post('/api/reception/appointments',json={**self.body,**changes},headers=self.headers[actor])
    def action(self,id,status,actor='receptionist'):
        return self.client.post(f'/api/reception/appointments/{id}/status',json={'status':status},headers=self.headers[actor])
    def test_role_authorization_and_clinical_grant_denial(self):
        for actor in ('owner','other','doctor','admin'):
            self.assertEqual(self.create(actor).status_code,403)
            for path in ('/api/reception/appointments','/api/reception/doctors','/api/reception/patients?email=owner@example.invalid'):
                self.assertEqual(self.client.get(path,headers=self.headers[actor]).status_code,403)
        self.assertEqual(self.client.get('/api/reception/appointments').status_code,401)
        for method,path,payload in patient_tests.PatientApiTests.operations(self):
            self.assertEqual(self.client.open(path,method=method,json=payload,headers=self.headers['receptionist']).status_code,403)
        path=f'/api/patients/{self.patient.id}/doctor-access-grants'
        self.assertEqual(self.client.get(path,headers=self.headers['receptionist']).status_code,403)
        self.assertEqual(self.client.post(path,json={},headers=self.headers['receptionist']).status_code,403)
        self.assertEqual(self.client.post(path+'/1/revoke',json={},headers=self.headers['receptionist']).status_code,403)
    def test_lookup_is_exact_and_only_administrative_fields(self):
        response=self.client.get('/api/reception/patients?email=OWNER@example.invalid',headers=self.headers['receptionist'])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json(),{'patient':{'id':self.patient.id,'email':'owner@example.invalid','administrative_status':'registered'}})
        for email in ('own@example.invalid','owner','doctor@example.invalid'):
            self.assertIn(self.client.get('/api/reception/patients?email='+email,headers=self.headers['receptionist']).status_code,(400,404))
        self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_default_duration_and_explicit_timezone_roundtrip(self):
        response=self.create();self.assertEqual(response.status_code,201)
        row=response.get_json()['appointment']
        self.assertEqual(row['starts_at'],'2026-11-01T04:30:00Z');self.assertEqual(row['ends_at'],'2026-11-01T05:00:00Z')
        self.assertEqual(row['created_by_user_id'],self.users['receptionist'].id)
        self.assertEqual(db.session.query(AppointmentEvent).count(),1)
        self.assertEqual(self.client.get('/api/reception/appointments',headers=self.headers['second_receptionist']).get_json()['appointments'],[row])
    def test_overlap_doctor_patient_adjacent_and_terminal_slots(self):
        first=self.create().get_json()['appointment']
        self.assertEqual(self.create(patient_id=self.other_patient.id).status_code,409);db.session.rollback()
        self.assertEqual(self.create(doctor_user_id=self.users['doctor2'].id).status_code,409);db.session.rollback()
        self.assertEqual(self.create(starts_at='2026-11-01T05:00:00Z').status_code,201)
        self.assertEqual(self.action(first['id'],'cancelled').status_code,200)
        self.assertEqual(self.create().status_code,201)
    def test_timestamp_and_participant_validation(self):
        for changes in ({'starts_at':'bad'},{'starts_at':'2026-11-01T10:00:00'},
            {'ends_at':'2026-11-01T04:30:00Z'},{'ends_at':'2026-11-01T04:00:00Z'},
            {'patient_id':True},{'doctor_user_id':self.users['admin'].id},{'patient_id':999},
            {'status':'completed'},{'created_by_user_id':self.users['owner'].id}):
            self.assertEqual(self.create(**changes).status_code,400);db.session.rollback()
        self.assertEqual(db.session.query(Appointment).count(),0)
    def test_reschedule_by_any_receptionist_and_conflict(self):
        first=self.create().get_json()['appointment']
        second=self.create(starts_at='2026-11-01T06:00:00Z').get_json()['appointment']
        path=f'/api/reception/appointments/{first["id"]}/reschedule'
        self.assertEqual(self.client.post(path,json={'starts_at':second['starts_at']},headers=self.headers['second_receptionist']).status_code,409);db.session.rollback()
        response=self.client.post(path,json={'starts_at':'2026-11-02T10:00:00Z','ends_at':'2026-11-02T10:45:00Z'},headers=self.headers['second_receptionist'])
        self.assertEqual(response.status_code,200);self.assertEqual(response.get_json()['appointment']['updated_by_user_id'],self.users['second_receptionist'].id)
    def test_every_allowed_and_forbidden_transition(self):
        from backend.app.api.reception import TRANSITIONS
        paths={'scheduled':[], 'checked_in':['checked_in'], 'completed':['checked_in','completed'], 'cancelled':['cancelled'], 'no_show':['no_show']}
        statuses=tuple(paths)
        for index,(state,actions) in enumerate(paths.items()):
            for target in statuses:
                row=self.create(starts_at=f'2026-11-{index+3:02}T{statuses.index(target):02}:00:00Z').get_json()['appointment']
                for action in actions:self.assertEqual(self.action(row['id'],action).status_code,200)
                result=self.action(row['id'],target)
                self.assertEqual(result.status_code,200 if target in TRANSITIONS.get(state,set()) else 409);db.session.rollback()
                if state!='scheduled':
                    self.assertEqual(self.client.post(f'/api/reception/appointments/{row["id"]}/reschedule',json={'starts_at':'2026-12-01T10:00:00Z'},headers=self.headers['receptionist']).status_code,409);db.session.rollback()
    def test_provisioning_and_public_role_injection(self):
        runner=self.app.test_cli_runner()
        result=runner.invoke(args=['create-privileged-user','--email','provisioned-rec@example.invalid','--role','receptionist'],input='test-password-strong-123\ntest-password-strong-123\n')
        self.assertEqual(result.exit_code,0)
        self.assertEqual(self.client.post('/api/auth/register',json={'email':'inject@example.invalid','password':'test-password-strong-123','role':'receptionist'}).status_code,400)
    def test_schema_agreement_and_fk_enforcement_restored(self):
        with db.engine.connect() as connection:
            self.assertEqual(compare_metadata(MigrationContext.configure(connection),db.metadata),[])
            self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(),1)

class ReceptionMigrationConcurrencyTests(unittest.TestCase):
    def test_existing_rows_survive_role_rebuild_and_concurrent_overlap_is_serialized(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'.local') as folder:
            path=Path(folder)/'fixture.sqlite3';engine=create_engine('sqlite:///'+path.as_posix());enable_sqlite_foreign_keys(engine)
            try:
                with engine.begin() as connection:
                    command.upgrade(migration_config(connection),'0005_patient_doctor_grants')
                    connection.exec_driver_sql("INSERT INTO users (id,email,role_id) VALUES (1,'existing@example.invalid',1)")
                    connection.exec_driver_sql('INSERT INTO patients (id,owner_user_id) VALUES (1,1)')
                with engine.begin() as connection:
                    command.upgrade(migration_config(connection),'head')
                    self.assertEqual(connection.exec_driver_sql('SELECT owner_user_id FROM patients WHERE id=1').scalar(),1)
                    self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall(),[])
                with engine.connect() as connection:self.assertEqual(connection.exec_driver_sql('PRAGMA foreign_keys').scalar(),1)
            finally:engine.dispose()
            app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+path.as_posix(),'JWT_SECRET_KEY':'isolated-reception-fixture-ABC0123456789'})
            with app.app_context():
                from backend.app.auth.security import hash_password
                hashed=hash_password('synthetic-concurrency-password')
                doctor=User(email='doc@example.invalid',role_id=2,password_hash=hashed)
                reception=User(email='rec@example.invalid',role_id=4,password_hash=hashed)
                db.session.add_all([doctor,reception]);db.session.commit()
                doctor_id=doctor.id;token=issue_token(reception)
            barrier=threading.Barrier(2)
            def book(_):
                with app.test_client() as client:
                    barrier.wait(timeout=5)
                    return client.post('/api/reception/appointments',json={'patient_id':1,'doctor_user_id':doctor_id,'starts_at':'2026-12-01T10:00:00Z'},headers={'Authorization':'Bearer '+token}).status_code
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(book,range(2)))
                self.assertEqual(sorted(results),[201,409])
                with app.app_context():self.assertEqual(db.session.query(Appointment).count(),1)
            finally:
                with app.app_context():db.session.remove();db.engine.dispose()
