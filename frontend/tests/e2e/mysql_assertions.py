"""Focused assertions against the already identity-checked disposable schema."""
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.database import db
from backend.app.models import User, ClinicalAssessment
from backend.app.auth.routes import create_account
from backend.app.auth.security import issue_token
from backend.app.auth.grants import utc_now
from backend.app.api.assessment_validation import CATEGORICAL_INPUTS, NUMERIC_INPUTS


def verify_mysql(app):
    client = app.test_client()
    with app.app_context():
        assert db.engine.dialect.name == 'mysql'
        owner = create_account('mysql-probe-patient@example.invalid', 'fixture-password-123', 'patient')
        doctor = create_account('mysql-probe-doctor@example.invalid', 'fixture-password-123', 'doctor')
        admin = db.session.scalar(select(User).where(User.email == 'admin@example.invalid'))
        patient_id, owner_id, doctor_id = owner.patient.id, owner.id, doctor.id
        headers = {name: {'Authorization': 'Bearer ' + issue_token(user)}
            for name, user in [('owner', owner), ('doctor', doctor), ('admin', admin)]}
        # Actual unique constraint violation, rollback, then successful use of session.
        db.session.add(User(email=owner.email, role_id=1, password_hash=owner.password_hash))
        try:
            db.session.commit()
            raise AssertionError('MySQL unique email constraint did not reject duplicate')
        except IntegrityError:
            db.session.rollback()
        assert db.session.scalar(select(User.id).where(User.email == 'mysql-probe-patient@example.invalid')) == owner_id
        legacy = ClinicalAssessment(patient_id=patient_id, recorded_by_user_id=owner_id, inputs=None, notes=None)
        db.session.add(legacy)
        db.session.commit()
        assert legacy.patient.owner.id == owner_id and legacy.recorded_by.id == owner_id
        legacy_id = legacy.id
    url = f'/api/patients/{patient_id}/assessments'
    inputs = {**{name: 'Synthetic MySQL probe' for name in CATEGORICAL_INPUTS},
              **{name: 0 for name in NUMERIC_INPUTS}}
    for _ in range(21):
        result = client.post(url, json={'inputs': inputs, 'notes': None, 'predict': False}, headers=headers['owner'])
        assert result.status_code == 201
        saved = result.get_json()['assessment']
        assert saved['inputs'] == inputs and saved['notes'] is None and saved['created_at']
    first = client.get(url, headers=headers['owner']).get_json()
    assert len(first['assessments']) == 20 and first['next_after_id'] == first['assessments'][-1]['id']
    second = client.get(url + '?after_id=' + str(first['next_after_id']), headers=headers['owner']).get_json()
    rows = first['assessments'] + second['assessments']
    assert len(rows) == 22 and len({row['id'] for row in rows}) == 22
    assert [row['id'] for row in rows] == sorted(row['id'] for row in rows) and second['next_after_id'] is None
    detail = client.get(url + '/' + str(legacy_id), headers=headers['owner']).get_json()['assessment']
    assert detail['inputs'] is None and detail['notes'] is None
    start = utc_now()
    grant_url = f'/api/patients/{patient_id}/doctor-access-grants'
    with patch('backend.app.api.access_grants.utc_now', return_value=start):
        result = client.post(grant_url, json={'doctor_user_id': doctor_id,
            'consent_reference': 'synthetic-mysql-probe'}, headers=headers['admin'])
    assert result.status_code == 201
    grant = result.get_json()['grant']
    assert grant['issued_at'].endswith('Z') and grant['expires_at'].endswith('Z')
    for instant, allowed in [(start, True), (start + timedelta(days=30, seconds=-1), True),
        (start + timedelta(days=30), False)]:
        with patch('backend.app.auth.grants.utc_now', return_value=instant):
            directory = client.get('/api/patients/authorized', headers=headers['doctor']).get_json()['patients']
            assert directory == ([{'id': patient_id}] if allowed else [])
            assert client.get(url, headers=headers['doctor']).status_code == (200 if allowed else 403)
    with patch('backend.app.api.access_grants.utc_now', return_value=start):
        assert client.post(grant_url + '/' + str(grant['id']) + '/revoke', json={}, headers=headers['owner']).status_code == 200
    assert client.get(url, headers=headers['doctor']).status_code == 403
    assert client.get('/api/patients/authorized', headers=headers['doctor']).get_json()['patients'] == []
    return ['relationships', 'unique_constraint_rollback', 'committed_assessments',
        'nullable_json_notes', 'history_keyset_ordering', 'grant_expiry_boundary', 'grant_revocation']
