"""Synthetic approved reports, real ReportLab/HTTP/SQLite; no ML execution."""
from hashlib import sha256
from unittest.mock import patch
import unittest

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, inspect
from sqlalchemy.exc import OperationalError

from backend.app.database import db
from backend.app.models import ClinicalReport, ClinicalAssessment
from backend.app.services.report_storage import MemoryReportStorage
import test_clinical_reviews as reviews
from test_database import migration_config


class ClinicalReportTests(unittest.TestCase):
    setUpClass = classmethod(reviews.ClinicalReviewTests.setUpClass.__func__)
    grant = reviews.ClinicalReviewTests.grant
    save = reviews.ClinicalReviewTests.save

    def setUp(self):
        reviews.ClinicalReviewTests.setUp(self)
        self.store = MemoryReportStorage()
        self.app.extensions['report_storage'] = self.store
        self.app.config['REPORT_SIGNING_KEY'] = 'synthetic-report-signing-key-only-' * 2
        self.report_url = self.review_url.removesuffix('/reviews') + '/report'

    def issue(self, actor='doctor'):
        return self.client.post(self.report_url, json={}, headers=self.headers[actor])

    def link(self, actor='doctor'):
        return self.client.post(self.report_url+'/download-link', json={}, headers=self.headers[actor])

    def content(self, link, actor='doctor'):
        return self.client.get(self.report_url+'/content', headers={**self.headers[actor], 'X-Report-Link':link['url'].split('#')[1]})

    def approved(self):
        self.grant(); self.assertEqual(self.save().status_code,201)

    def test_approved_pdf_persists_metadata_and_reloads_for_owner(self):
        self.approved()
        issued=self.issue(); self.assertEqual(issued.status_code,201)
        self.assertEqual(issued.headers['Cache-Control'],'no-store')
        row=db.session.scalar(select(ClinicalReport))
        blob=self.store.get(row.object_key)
        self.assertTrue(blob.startswith(b'%PDF-')); self.assertIn(b'AYUR-SAGE',blob)
        for text in (b'SYNTHETIC doctor review', b'SYNTHETIC medicine', b'SYNTHETIC manual recommendation'):
            self.assertIn(text,blob)
        self.assertEqual(row.sha256,sha256(blob).hexdigest()); self.assertEqual(row.byte_length,len(blob))
        self.assertEqual(row.version,1); self.assertEqual(len(row.snapshot_sha256),64)
        self.assertEqual(row.issued_by_user_id,self.users['doctor'].id)
        self.assertNotIn('object_key',issued.get_json()['report'])
        db.session.remove()
        self.assertEqual(self.client.get(self.report_url,headers=self.headers['owner']).get_json()['status'],'available')
        link=self.link('owner'); self.assertEqual(link.status_code,200)
        self.assertEqual(link.get_json()['expires_in'],900)
        content=self.content(link.get_json(),'owner')
        self.assertEqual(content.data,blob); self.assertEqual(content.mimetype,'application/pdf')
        self.assertEqual(content.headers['Cache-Control'],'no-store')
        self.assertEqual(self.issue('owner').status_code,403)

    def test_preapproval_and_read_only_grants_cannot_issue_or_download(self):
        grant=self.grant(False)
        for method,suffix in [('get',''),('post',''),('post','/download-link'),('get','/content')]:
            self.assertEqual(getattr(self.client,method)(self.report_url+suffix,json={} if method=='post' else None,headers=self.headers['doctor']).status_code,403)
        self.client.post(self.grant_url+f"/{grant['id']}/revoke",json={},headers=self.headers['owner'])
        self.client.post(self.grant_url,json={'doctor_user_id':self.users['doctor'].id,'consent_reference':'synthetic-new','allow_review':True},headers=self.headers['admin'])
        self.assertEqual(self.issue().status_code,409)
        self.assertEqual(self.link().status_code,404)
        self.assertEqual(self.client.get(self.report_url,headers=self.headers['owner']).get_json()['status'],'awaiting_approval')
        self.assertFalse(self.store._objects)

    def test_cross_patient_roles_and_revoked_doctor_are_denied(self):
        self.approved(); self.issue(); link=self.link().get_json()
        for actor in ('other','other_doctor','admin','receptionist'):
            self.assertEqual(self.issue(actor).status_code,403)
            self.assertEqual(self.client.get(self.report_url,headers=self.headers[actor]).status_code,403)
            self.assertEqual(self.link(actor).status_code,403)
            self.assertEqual(self.content(link,actor).status_code,403)
        self.assertEqual(self.client.get(self.report_url).status_code,401)
        wrong=self.other_url+f"/{self.assessment['id']}/report"
        self.assertEqual(self.client.get(wrong,headers=self.headers['other']).status_code,404)
        grant=self.client.get(self.grant_url,headers=self.headers['owner']).get_json()['grants'][0]
        self.client.post(self.grant_url+f"/{grant['id']}/revoke",json={},headers=self.headers['owner'])
        self.assertEqual(self.issue().status_code,403); self.assertEqual(self.link().status_code,403)
        self.assertEqual(self.content(link).status_code,403)
        self.assertEqual(self.link('owner').status_code,200)
        response=self.client.post(self.grant_url,json={'doctor_user_id':self.users['doctor'].id,
            'consent_reference':'synthetic-read-only-after-issue','allow_review':False},headers=self.headers['admin'])
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.client.get(self.report_url,headers=self.headers['doctor']).status_code,403)
        self.assertEqual(self.content(link).status_code,403)

    def test_links_expire_at_900_seconds_and_cannot_be_transferred_or_tampered(self):
        self.approved(); self.issue()
        with patch('itsdangerous.timed.time.time',return_value=1000): link=self.link().get_json()
        with patch('itsdangerous.timed.time.time',return_value=1900): self.assertEqual(self.content(link).status_code,200)
        with patch('itsdangerous.timed.time.time',return_value=1901): self.assertEqual(self.content(link).status_code,403)
        self.assertEqual(self.content(self.link().get_json(),'owner').status_code,403)
        bad={'url':self.link().get_json()['url']+'tampered'}
        self.assertEqual(self.content(bad).status_code,403)
        self.assertEqual(self.client.get(self.report_url+'/content',headers=self.headers['doctor']).status_code,403)

    def test_repeat_issue_preserves_object_and_original_snapshot(self):
        self.approved(); first=self.issue().get_json()
        row=db.session.scalar(select(ClinicalReport)); original=self.store.get(row.object_key)
        assessment=db.session.get(ClinicalAssessment,self.assessment['id']); assessment.notes='later synthetic note'; db.session.commit()
        repeated=self.issue(); self.assertEqual(repeated.status_code,200); self.assertEqual(repeated.get_json(),first)
        self.assertEqual(self.store.get(row.object_key),original); self.assertEqual(len(self.store._objects),1)
        row.version=2
        with self.assertRaises(ValueError): db.session.commit()
        db.session.rollback()

    def test_pdf_upload_database_failures_leave_no_available_report_and_recover(self):
        self.approved()
        for target,kwargs in [('backend.app.api.clinical_reports.generate_pdf',{'side_effect':RuntimeError('SYNTHETIC private clinical content')})]:
            with patch(target,**kwargs): self.assertEqual(self.issue().status_code,503)
        real_put=self.store.put
        def partial(key,content): real_put(key,content); raise RuntimeError('SYNTHETIC private credential')
        with patch.object(self.store,'put',side_effect=partial): self.assertEqual(self.issue().status_code,503)
        self.assertFalse(self.store._objects)
        with patch.object(db.session,'commit',side_effect=OperationalError('TEST',{},Exception('SYNTHETIC private data'))):
            self.assertEqual(self.issue().status_code,503)
        self.assertFalse(self.store._objects); self.assertEqual(db.session.query(ClinicalReport).count(),0)
        self.assertEqual(self.issue().status_code,201)

    def test_storage_signing_and_integrity_failures_are_safe(self):
        self.approved()
        self.app.extensions.pop('report_storage'); self.assertEqual(self.issue().status_code,503)
        self.app.extensions['report_storage']=self.store
        self.app.config['REPORT_SIGNING_KEY']=None; self.assertEqual(self.issue().status_code,503)
        self.app.config['REPORT_SIGNING_KEY']='synthetic-signing-key-'*3; self.assertEqual(self.issue().status_code,201)
        with patch('backend.app.api.clinical_reports.URLSafeTimedSerializer.dumps',side_effect=RuntimeError('secret')):
            self.assertEqual(self.link().status_code,503)
        row=db.session.scalar(select(ClinicalReport)); self.store._objects[row.object_key]=b'corrupt'
        self.assertEqual(self.link().status_code,503)
        self.assertEqual(self.client.get(self.report_url,headers=self.headers['owner']).status_code,503)

    def test_failures_never_log_content_credentials_or_signed_links(self):
        self.approved()
        with self.assertLogs(self.app.logger,level='WARNING') as logs:
            with patch('backend.app.api.clinical_reports.generate_pdf',side_effect=RuntimeError('PRIVATE clinical prescription credential')):
                self.assertEqual(self.issue().status_code,503)
        self.assertNotIn('PRIVATE',' '.join(logs.output))
        self.issue(); signed=self.link().get_json()['url']
        with self.assertLogs(self.app.logger,level='WARNING') as logs:
            with patch.object(self.store,'get',side_effect=RuntimeError(signed)):
                self.assertEqual(self.content({'url':signed}).status_code,503)
        self.assertNotIn(signed,' '.join(logs.output))

    def test_migration_matches_models_and_roundtrips_without_touching_review(self):
        self.approved()
        with db.engine.begin() as connection:
            self.assertEqual(compare_metadata(MigrationContext.configure(connection),db.metadata),[])
            command.downgrade(migration_config(connection),'0007_clinical_review')
            self.assertNotIn('clinical_reports',inspect(connection).get_table_names())
            command.upgrade(migration_config(connection),'head')
        self.assertEqual(self.client.get(self.review_url,headers=self.headers['doctor']).get_json()['state'],'approved')

    def test_lost_commit_acknowledgement_retains_committed_pdf_and_retry_is_idempotent(self):
        self.approved(); commit=db.session.commit
        def lost_ack():
            commit()
            raise OperationalError('TEST',{},Exception('lost acknowledgement'))
        with patch.object(db.session,'commit',side_effect=lost_ack):
            self.assertEqual(self.issue().status_code,503)
        self.assertEqual(db.session.query(ClinicalReport).count(),1)
        self.assertEqual(len(self.store._objects),1)
        self.assertEqual(self.issue().status_code,200)
        self.assertEqual(self.link('owner').status_code,200)

    def test_failed_cleanup_is_reported_without_incomplete_metadata_and_retry_recovers(self):
        self.approved(); put=self.store.put
        def partial(key,content): put(key,content); raise RuntimeError('private upload failure')
        with self.assertLogs(self.app.logger,level='WARNING') as logs:
            with patch.object(self.store,'put',side_effect=partial), patch.object(self.store,'delete',side_effect=RuntimeError('private cleanup failure')):
                self.assertEqual(self.issue().status_code,503)
        self.assertIn('orphan_cleanup_required',' '.join(logs.output))
        self.assertNotIn('private',' '.join(logs.output)); self.assertEqual(db.session.query(ClinicalReport).count(),0)
        self.assertEqual(self.client.get(self.report_url,headers=self.headers['owner']).get_json()['status'],'not_issued')
        self.assertEqual(self.issue().status_code,201)

    def test_large_escaped_and_unsupported_text_never_silently_changes_content(self):
        self.grant()
        payload=reviews.review_payload(clinical_notes='<img src="https://invalid.example/">'+' Long synthetic note.'*180)
        self.assertEqual(self.save(payload).status_code,201); self.assertEqual(self.issue().status_code,201)
        content=self.content(self.link().get_json()).data
        self.assertGreater(content.count(b'/Type /Page'),2)
        from backend.app.services.clinical_pdf import generate_pdf
        with self.assertRaises(ValueError):
            generate_pdf({'patient_id':'\U0001f9ec','assessment_id':1})


if __name__=='__main__': unittest.main()
