"""Approval-gated issuance and reauthorized private retrieval; never calls ML."""
from functools import wraps
from hashlib import sha256
import json
from uuid import uuid4

from flask import current_app, g, request, Response
from itsdangerous import URLSafeTimedSerializer, BadData
from sqlalchemy import insert, select
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, HTTPException, NotFound, ServiceUnavailable

from backend.app.auth.security import roles_required, require_patient_owner
from backend.app.auth.grants import utc_now
from backend.app.database import db
from backend.app.models import ClinicalAssessment, ClinicalReport, Patient
from backend.app.services.clinical_pdf import generate_pdf
from .clinical_reviews import record, review_data, review_permission
from .assessment_validation import json_object
from .patients import patients

LINK_SECONDS = 900


def safe_report_operation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except HTTPException:
            raise
        except Exception:
            # Provider/renderer exceptions can embed clinical content or credentials.
            db.session.rollback()
            current_app.logger.warning('clinical_report_operation_failed')
            raise ServiceUnavailable() from None
    return wrapped


def authorized_assessment(patient_id, assessment_id, *, lock=False):
    if request.args:
        raise BadRequest()
    if not all(1 <= value <= 2147483647 for value in (patient_id, assessment_id)):
        raise NotFound()
    if g.current_user.role.code == 'doctor':
        if not review_permission(patient_id, lock=lock):
            raise Forbidden()
        return record(patient_id, assessment_id, lock=lock)
    require_patient_owner(db.session.get(Patient, patient_id))
    assessment = db.session.scalar(select(ClinicalAssessment).where(
        ClinicalAssessment.id == assessment_id, ClinicalAssessment.patient_id == patient_id))
    if assessment is None:
        raise NotFound()
    return assessment


def report_for(assessment):
    if assessment.review_state != 'approved':
        return None
    row = db.session.scalar(select(ClinicalReport).where(ClinicalReport.assessment_id == assessment.id))
    if row and row.review_id != assessment.review_history[-1].id:
        raise ServiceUnavailable()
    return row


def metadata(row):
    return {'id': row.id, 'version': row.version, 'assessment_id': row.assessment_id,
        'review_id': row.review_id, 'issued_at': row.issued_at.isoformat() + 'Z',
        'issued_by_user_id': row.issued_by_user_id, 'sha256': row.sha256, 'byte_length': row.byte_length}


def storage():
    value = current_app.extensions.get('report_storage')
    if value is None:
        raise ServiceUnavailable()
    return value


def signer():
    key = current_app.config.get('REPORT_SIGNING_KEY')
    if not isinstance(key, str) or len(key) < 32:
        raise ServiceUnavailable()
    return URLSafeTimedSerializer(key, salt='ayur-sage-clinical-report-v1')


def stored_content(row):
    content = storage().get(row.object_key)
    if not isinstance(content, bytes) or len(content) != row.byte_length or sha256(content).hexdigest() != row.sha256:
        raise ServiceUnavailable()
    return content


@patients.get('/<int:patient_id>/assessments/<int:assessment_id>/report')
@roles_required('doctor', 'patient')
@safe_report_operation
def report_availability(patient_id, assessment_id):
    assessment = authorized_assessment(patient_id, assessment_id)
    row = report_for(assessment)
    if row:
        stored_content(row)
    return {'status': 'available' if row else 'not_issued' if assessment.review_state == 'approved' else 'awaiting_approval',
        'can_generate': g.current_user.role.code == 'doctor' and assessment.review_state == 'approved' and row is None,
        'report': metadata(row) if row else None}


@patients.post('/<int:patient_id>/assessments/<int:assessment_id>/report')
@roles_required('doctor')
@safe_report_operation
def issue_report(patient_id, assessment_id):
    assessment = authorized_assessment(patient_id, assessment_id, lock=True)
    if json_object() != {}:
        raise BadRequest()
    if assessment.review_state != 'approved':
        raise Conflict()
    existing = report_for(assessment)
    if existing:
        stored_content(existing)
        return {'report': metadata(existing)}, 200
    store = storage()
    signer()  # Do not issue an object that cannot be retrieved in this deployment.
    now = utc_now()
    approval = assessment.review_history[-1]
    snapshot = {'patient_id': patient_id, 'assessment_id': assessment.id,
        'assessed_at': assessment.created_at.isoformat(), 'inputs': assessment.inputs,
        'patient_notes': assessment.notes, 'approval': review_data(approval),
        'history': [review_data(row) for row in assessment.review_history], 'issued_at': now.isoformat() + 'Z'}
    # Detach JSON values before rendering, under the assessment/grant transaction.
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
    content = generate_pdf(json.loads(encoded))
    if not isinstance(content, bytes) or not content.startswith(b'%PDF-'):
        raise ServiceUnavailable()
    key = 'clinical-reports/' + uuid4().hex + '.pdf'
    commit_attempted = False
    try:
        store.put(key, content)
        result = db.session.connection().execute(insert(ClinicalReport.__table__).values(
            assessment_id=assessment.id, review_id=approval.id, issued_by_user_id=g.current_user.id,
            version=1, object_key=key, sha256=sha256(content).hexdigest(), snapshot_sha256=sha256(encoded).hexdigest(),
            byte_length=len(content), issued_at=now))
        row = db.session.get(ClinicalReport, result.inserted_primary_key[0])
        response = metadata(row)
        commit_attempted = True
        db.session.commit()
    except Exception:
        db.session.rollback()
        safe_to_delete = not commit_attempted
        if commit_attempted:
            try:
                # A lost commit acknowledgement must not delete a committed PDF.
                safe_to_delete = db.session.scalar(select(ClinicalReport.id).where(ClinicalReport.object_key == key)) is None
            except Exception:
                db.session.rollback()
        if safe_to_delete:
            try:
                store.delete(key)
            except Exception:
                current_app.logger.error('clinical_report_orphan_cleanup_required key=%s', key)
        else:
            current_app.logger.warning('clinical_report_commit_reconciliation_required key=%s', key)
        raise
    return {'report': response}, 201


@patients.post('/<int:patient_id>/assessments/<int:assessment_id>/report/download-link')
@roles_required('doctor', 'patient')
@safe_report_operation
def report_link(patient_id, assessment_id):
    assessment = authorized_assessment(patient_id, assessment_id)
    if json_object() != {}:
        raise BadRequest()
    row = report_for(assessment)
    if row is None:
        raise NotFound()
    stored_content(row)
    token = signer().dumps({'report_id': row.id, 'user_id': g.current_user.id, 'sha256': row.sha256})
    # Fragments are not sent in HTTP request targets, proxy logs or Referer headers.
    path = f'/patients/{patient_id}/assessments/{assessment_id}/report/content'
    return {'url': path + '#' + token, 'expires_in': LINK_SECONDS}


@patients.get('/<int:patient_id>/assessments/<int:assessment_id>/report/content')
@roles_required('doctor', 'patient')
@safe_report_operation
def report_content(patient_id, assessment_id):
    assessment = authorized_assessment(patient_id, assessment_id)
    row = report_for(assessment)
    if row is None:
        raise NotFound()
    token = request.headers.get('X-Report-Link', '')
    if not token or len(token) > 2048:
        raise Forbidden()
    try:
        claims = signer().loads(token, max_age=LINK_SECONDS)
    except BadData:
        raise Forbidden() from None
    if claims != {'report_id': row.id, 'user_id': g.current_user.id, 'sha256': row.sha256}:
        raise Forbidden()
    response = Response(stored_content(row), mimetype='application/pdf')
    response.headers['Content-Disposition'] = 'attachment; filename="ayur-sage-clinical-report-v1.pdf"'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response
