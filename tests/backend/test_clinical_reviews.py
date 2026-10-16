"""Human-authored review HTTP tests on migrated disposable in-memory SQLite."""
from copy import deepcopy
from datetime import timedelta
import unittest
from unittest.mock import patch

from alembic import command
from sqlalchemy import inspect, select, update
from sqlalchemy.exc import OperationalError

from backend.app.database import db
from backend.app.models import AssessmentReview, ClinicalAssessment, GrantAdministrator, PatientDoctorGrant, User
from backend.app.auth.grants import utc_now
from backend.app.auth.security import issue_token
from backend.app.api.assessment_validation import OUTPUT_TARGETS
from backend.app.services.v17 import V17Service
from test_database import migration_config
import test_patients as existing


def review_payload(**changes):
    return {"expected_version": 0, "decision": "approved", "clinical_notes": "SYNTHETIC doctor review",
        "recommendations": {name: "SYNTHETIC manual recommendation" for name in OUTPUT_TARGETS},
        "prescriptions": [{"medication": "SYNTHETIC medicine", "dose": "SYNTHETIC dose", "route": "SYNTHETIC route",
            "frequency": "SYNTHETIC frequency", "duration": "SYNTHETIC duration", "instructions": ""}], **changes}


class ClinicalReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing.PatientApiTests.setUpClass.__func__(cls)

    def setUp(self):
        for method in ("load", "predict"):
            guard=patch.object(V17Service,method,side_effect=AssertionError('V17 execution forbidden'))
            guard.start(); self.addCleanup(guard.stop)
        existing.PatientApiTests.setUp(self)
        db.session.add(GrantAdministrator(user_id=self.users['admin'].id, authorized_at=utc_now()))
        for name,role in (("other_doctor",2),("receptionist",4)):
            user=User(email=name+'@example.invalid',role_id=role,password_hash=self.password_hash)
            db.session.add(user); db.session.flush()
            self.users[name]=user; self.headers[name]={"Authorization":"Bearer "+issue_token(user)}
        db.session.commit()
        self.assessment=self.client.post(self.url,json=existing.valid_payload(),headers=self.headers['owner']).get_json()['assessment']
        self.review_url=self.url+f"/{self.assessment['id']}/reviews"
        self.grant_url=f"/api/patients/{self.patient.id}/doctor-access-grants"

    def grant(self, allow=True):
        response=self.client.post(self.grant_url,json={"doctor_user_id":self.users['doctor'].id,
            "consent_reference":"synthetic-consent-001","allow_review":allow},headers=self.headers['admin'])
        self.assertEqual(response.status_code,201)
        return response.get_json()['grant']

    def save(self, payload=None, actor='doctor'):
        return self.client.post(self.review_url,json=review_payload() if payload is None else payload,headers=self.headers[actor])

    def test_save_persists_human_content_actor_time_and_reload(self):
        self.grant()
        response=self.save(); self.assertEqual(response.status_code,201)
        data=response.get_json(); self.assertEqual(data['state'],'approved'); self.assertEqual(data['version'],1)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        row=data['reviews'][0]
        self.assertEqual(row['actor_user_id'],self.users['doctor'].id)
        self.assertTrue(row['decided_at'].endswith('Z')); self.assertEqual(row['origin'],'doctor_entered')
        for key in ('clinical_notes','recommendations','prescriptions'):
            self.assertEqual(row[key],review_payload()[key])
        db.session.remove()
        self.assertEqual(self.client.get(self.review_url,headers=self.headers['doctor']).get_json(),data)
        saved=db.session.scalar(select(AssessmentReview))
        self.assertEqual(saved.prescriptions,review_payload()['prescriptions'])
        original=db.session.get(ClinicalAssessment,self.assessment['id'])
        self.assertEqual(original.inputs,existing.valid_payload()['inputs'])
        self.assertEqual(original.notes,existing.valid_payload()['notes'])

    def test_read_only_grant_does_not_authorize_review(self):
        grant=self.grant(False); self.assertFalse(grant['allow_review'])
        response=self.client.get(self.review_url,headers=self.headers['doctor'])
        self.assertEqual(response.status_code,200); self.assertFalse(response.get_json()['can_review'])
        self.assertEqual(self.save().status_code,403)
        self.assertEqual(db.session.query(AssessmentReview).count(),0)

    def test_roles_and_unrelated_doctor_denied_on_reads_and_writes(self):
        self.grant()
        for actor in ('owner','other','admin','receptionist','other_doctor'):
            self.assertEqual(self.save(actor=actor).status_code,403)
            self.assertEqual(self.client.get(self.review_url,headers=self.headers[actor]).status_code,403)
        for method in ('get','post'):
            self.assertEqual(getattr(self.client,method)(self.review_url).status_code,401)
        self.assertEqual(db.session.query(AssessmentReview).count(),0)

    def test_missing_and_cross_patient_assessments_rejected(self):
        self.grant()
        other=self.client.post(self.other_url,json=existing.valid_payload(),headers=self.headers['other']).get_json()['assessment']
        for ident in (other['id'],999999):
            url=self.url+f'/{ident}/reviews'
            self.assertEqual(self.client.get(url,headers=self.headers['doctor']).status_code,404)
            self.assertEqual(self.client.post(url,json=review_payload(),headers=self.headers['doctor']).status_code,404)
        url=self.other_url+f"/{self.assessment['id']}/reviews"
        self.assertEqual(self.client.post(url,json=review_payload(),headers=self.headers['doctor']).status_code,403)

    def test_revocation_denies_new_requests_but_retains_saved_history(self):
        grant=self.grant(); self.assertEqual(self.save().status_code,201)
        self.assertEqual(self.client.post(self.grant_url+f"/{grant['id']}/revoke",json={},headers=self.headers['owner']).status_code,200)
        self.assertEqual(self.client.get(self.review_url,headers=self.headers['doctor']).status_code,403)
        self.assertEqual(self.save().status_code,403)
        self.assertEqual(db.session.query(AssessmentReview).count(),1)

    def test_expiry_and_wrong_duration_do_not_authorize_writes(self):
        grant=self.grant(); table=PatientDoctorGrant.__table__
        for duration in (timedelta(days=30),timedelta(days=29)):
            now=utc_now(); issued=now-duration
            db.session.connection().execute(update(table).where(table.c.id==grant['id']).values(issued_at=issued,expires_at=now))
            db.session.commit()
            self.assertEqual(self.save().status_code,403)

    def test_invalid_payloads_and_prescriptions_never_write(self):
        self.grant()
        bad=[review_payload(expected_version=True),review_payload(expected_version=-1),review_payload(decision=[]),
            review_payload(clinical_notes=' '),review_payload(clinical_notes='x'*4097),review_payload(recommendations={}),
            review_payload(prescriptions={}),review_payload(prescriptions=[{}]),review_payload(prescriptions=[review_payload()['prescriptions'][0]]*11),
            {**review_payload(),'actor_user_id':self.users['admin'].id}]
        for key in review_payload():
            payload=review_payload(); del payload[key]; bad.append(payload)
        for key in ('dose','medication','duration'):
            payload=review_payload(); payload['prescriptions'][0][key]=False; bad.append(payload)
        for payload in bad:
            with self.subTest(payload=payload): self.assertEqual(self.save(payload).status_code,400)
        self.assertEqual(db.session.query(AssessmentReview).count(),0)

    def test_stale_duplicate_and_terminal_decisions_conflict(self):
        self.grant(); self.assertEqual(self.save().status_code,201)
        self.assertEqual(self.save().status_code,409)
        self.assertEqual(self.save(review_payload(expected_version=1)).status_code,409)
        self.assertEqual(db.session.query(AssessmentReview).count(),1)

    def test_return_revision_resubmission_preserves_previous_decisions(self):
        self.grant()
        self.assertEqual(self.save(review_payload(decision='returned_for_changes',prescriptions=[])).status_code,201)
        self.assertEqual(self.save(review_payload(expected_version=1)).status_code,409)
        self.assertEqual(self.save(review_payload(expected_version=1,decision='pending_review',clinical_notes='SYNTHETIC revised')).status_code,201)
        data=self.save(review_payload(expected_version=2)).get_json()
        self.assertEqual([row['decision'] for row in data['reviews']],['returned_for_changes','pending_review','approved'])
        self.assertEqual(data['reviews'][0]['prescriptions'],[])
        self.assertEqual(data['reviews'][1]['clinical_notes'],'SYNTHETIC revised')

    def test_grant_opt_in_is_boolean_admin_only_and_defaults_false(self):
        payload={"doctor_user_id":self.users['doctor'].id,"consent_reference":"synthetic"}
        for value in (None,1,'true',[]):
            self.assertEqual(self.client.post(self.grant_url,json={**payload,'allow_review':value},headers=self.headers['admin']).status_code,400)
        for actor in ('owner','doctor','receptionist'):
            self.assertEqual(self.client.post(self.grant_url,json={**payload,'allow_review':True},headers=self.headers[actor]).status_code,403)
        data=self.client.post(self.grant_url,json=payload,headers=self.headers['admin']).get_json()['grant']
        self.assertFalse(data['allow_review'])

    def test_commit_failure_does_not_return_or_persist_review(self):
        self.grant()
        with patch.object(db.session,'commit',side_effect=OperationalError('TEST',{},Exception('private'))):
            response=self.save()
        self.assertEqual(response.status_code,503)
        self.assertEqual(db.session.query(AssessmentReview).count(),0)
        self.assertEqual(self.save().status_code,201)

    def test_migration_roundtrip_and_legacy_read_grants_remain_read_only(self):
        self.grant(False)
        with db.engine.begin() as connection:
            command.downgrade(migration_config(connection),'0006_receptionist_appointments')
            self.assertNotIn('allow_review',{column['name'] for column in inspect(connection).get_columns('patient_doctor_grants')})
            command.upgrade(migration_config(connection),'head')
        db.session.expire_all()
        self.assertFalse(db.session.scalar(select(PatientDoctorGrant)).allow_review)
        self.assertEqual(self.save().status_code,403)


if __name__=='__main__': unittest.main()
