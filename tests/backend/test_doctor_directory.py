"""Real Flask/JWT queries over migrated, disposable in-memory SQLite only."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from sqlalchemy.dialects import mysql
from sqlalchemy.exc import OperationalError

from backend.app.database import db
from backend.app.models import Patient, User, PatientDoctorGrant, Appointment
from backend.app.auth.security import issue_token
from backend.app.auth.grants import assessment_read_grants
import test_patients as patient_tests


class DoctorDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        patient_tests.PatientApiTests.setUpClass.__func__(cls)

    def setUp(self):
        patient_tests.PatientApiTests.setUp(self)
        self.now = datetime(2026, 10, 15, 10)
        clock = patch('backend.app.auth.grants.utc_now', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        issue_clock = patch('backend.app.api.access_grants.utc_now', side_effect=lambda: self.now)
        issue_clock.start()
        self.addCleanup(issue_clock.stop)
        self.directory = '/api/patients/authorized'

    def grant(self, patient=None, doctor=None, **changes):
        patient = patient or self.patient
        row = PatientDoctorGrant(patient_id=patient.id,
            doctor_user_id=doctor or self.users['doctor'].id,
            consent_owner_user_id=patient.owner_user_id,
            consent_reference=f'synthetic-consent-{patient.id}',
            issuer_user_id=self.users['admin'].id, scope='assessment_read', status='issued',
            issued_at=self.now, expires_at=self.now + timedelta(days=30), active_slot=1)
        for name, value in changes.items():
            setattr(row, name, value)
        db.session.add(row)
        db.session.commit()
        return row

    def get(self, query='', actor='doctor'):
        return self.client.get(self.directory + query, headers=self.headers[actor])

    def new_patient(self, number):
        owner = User(email=f'directory-{number}@example.invalid', role_id=1, password_hash=self.password_hash)
        patient = Patient(owner=owner)
        db.session.add(patient)
        db.session.commit()
        return patient

    def test_only_current_doctors_granted_patients_and_minimal_fields(self):
        self.grant()
        other_doctor = User(email='other-doctor@example.invalid', role_id=2, password_hash=self.password_hash)
        db.session.add(other_doctor); db.session.commit()
        self.grant(self.other_patient, doctor=other_doctor.id)
        result = self.get()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json(), {'patients': [{'id': self.patient.id}], 'next_after_id': None})
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertNotIn('consent', result.get_data(as_text=True))
        headers = {'Authorization': 'Bearer ' + issue_token(other_doctor)}
        self.assertEqual(self.client.get(self.directory, headers=headers).get_json()['patients'], [{'id': self.other_patient.id}])

    def test_appointment_assignment_without_grant_does_not_authorize(self):
        db.session.add(Appointment(patient_id=self.patient.id, doctor_user_id=self.users['doctor'].id,
            starts_at=self.now, ends_at=self.now + timedelta(minutes=30), status='scheduled',
            created_by_user_id=self.users['admin'].id, updated_by_user_id=self.users['admin'].id,
            created_at=self.now, updated_at=self.now))
        db.session.commit()
        self.assertEqual(self.get().get_json(), {'patients': [], 'next_after_id': None})

    def test_revocation_excludes_patient_on_next_request_and_assessment_reads_stay_denied(self):
        row = self.grant()
        self.assertEqual(len(self.get().get_json()['patients']), 1)
        self.assertEqual(self.client.post(f'/api/patients/{self.patient.id}/doctor-access-grants/{row.id}/revoke',
            json={}, headers=self.headers['owner']).status_code, 200)
        self.assertEqual(self.get().get_json()['patients'], [])
        self.assertEqual(self.client.get(self.url, headers=self.headers['doctor']).status_code, 403)

    def test_issuance_and_exact_expiry_boundaries_use_existing_utc_policy(self):
        start = self.now
        self.grant()
        for instant, included in [(start - timedelta(seconds=1), False), (start, True),
            (start + timedelta(days=30, seconds=-1), True), (start + timedelta(days=30), False)]:
            self.now = instant
            self.assertEqual(bool(self.get().get_json()['patients']), included)
            self.assertEqual(self.client.get(self.url, headers=self.headers['doctor']).status_code, 200 if included else 403)

    def test_invalid_duration_owner_link_slot_and_whitespace_fail_closed_like_assessment_reads(self):
        invalid = [(self.patient, {'expires_at': self.now + timedelta(days=29)}),
            (self.other_patient, {'consent_owner_user_id': self.patient.owner_user_id}),
            (self.new_patient(1), {'active_slot': None}),
            (self.new_patient(2), {'consent_reference': '\t'})]
        for patient, changes in invalid:
            self.grant(patient, **changes)
            self.assertEqual(self.client.get(f'/api/patients/{patient.id}/assessments', headers=self.headers['doctor']).status_code, 403)
        self.assertEqual(self.get().get_json()['patients'], [])

    def test_authentication_role_and_caller_supplied_scope_cannot_bypass(self):
        self.assertEqual(self.client.get(self.directory).status_code, 401)
        self.assertEqual(self.client.get(self.directory, headers={'Authorization': 'Bearer invalid'}).status_code, 401)
        staff = User(email='directory-staff@example.invalid', role_id=4, password_hash=self.password_hash)
        db.session.add(staff); db.session.commit()
        self.headers['receptionist'] = {'Authorization': 'Bearer ' + issue_token(staff)}
        for actor in ['owner', 'admin', 'receptionist']:
            self.assertEqual(self.get(actor=actor).status_code, 403)
        self.assertEqual(self.get('?doctor_user_id=999').status_code, 400)
        self.assertEqual(self.get('?doctor_id=999').status_code, 400)
        self.assertEqual(self.get().get_json()['patients'], [])

    def test_keyset_pagination_is_ordered_bounded_and_excludes_invalid_rows(self):
        patients = [self.patient, self.other_patient] + [self.new_patient(i) for i in range(24)]
        for patient in reversed(patients):
            self.grant(patient)
        first = self.get().get_json()
        expected = sorted(patient.id for patient in patients)
        self.assertEqual([row['id'] for row in first['patients']], expected[:20])
        self.assertEqual(first['next_after_id'], expected[19])
        second = self.get(f"?after_id={first['next_after_id']}").get_json()
        self.assertEqual([row['id'] for row in second['patients']], expected[20:])
        self.assertIsNone(second['next_after_id'])
        for query in ['?after_id=-1', '?after_id=2147483648', '?after_id=x', '?after_id=0&after_id=1', '?limit=1000']:
            self.assertEqual(self.get(query).status_code, 400)

    def test_mysql_query_compiles_and_database_errors_are_generic(self):
        with self.app.test_request_context():
            from flask import g
            g.current_user = self.users['doctor']
            sql = str(assessment_read_grants(self.now).compile(dialect=mysql.dialect()))
            self.assertIn('patient_doctor_grants.doctor_user_id', sql)
            self.assertNotIn('julianday', sql)
        with patch('backend.app.api.patients.authorized_patient_page', side_effect=OperationalError('TEST', {}, Exception('PRIVATE'))):
            result = self.get()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('PRIVATE', result.get_data(as_text=True))
