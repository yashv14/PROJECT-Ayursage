"""Doctor-authored append-only decisions; never calls a prediction service."""
from flask import g, request
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from backend.app.auth.security import roles_required
from backend.app.auth.grants import assessment_read_patient, assessment_read_grants, utc_now, valid_grant_details
from backend.app.database import db
from backend.app.models import AssessmentReview, ClinicalAssessment, Patient
from backend.app.models.review import validate_review_transition
from .assessment_validation import json_object, valid_text, OUTPUT_TARGETS
from .patients import patients


PRESCRIPTION_FIELDS = ("medication", "dose", "route", "frequency", "duration", "instructions")


def review_permission(patient_id, *, lock=False):
    query = assessment_read_grants(utc_now()).where(Patient.id == patient_id)
    if lock:
        query = query.with_for_update()
    rows = db.session.execute(query).all()
    return any(row.allow_review is True and valid_grant_details(row) for row in rows)


def record(patient_id, assessment_id, *, lock=False):
    assessment_read_patient(patient_id)
    if not 1 <= assessment_id <= 2147483647:
        raise NotFound()
    query = select(ClinicalAssessment).where(ClinicalAssessment.patient_id == patient_id, ClinicalAssessment.id == assessment_id)
    if lock:
        query = query.with_for_update()
    row = db.session.scalar(query.execution_options(populate_existing=True))
    if row is None:
        raise NotFound()
    return row


def review_data(row):
    return {"id": row.id, "sequence": row.sequence, "actor_user_id": row.actor_user_id,
        "from_state": row.from_state, "decision": row.to_state,
        "decided_at": row.decided_at.isoformat() + "Z", "clinical_notes": row.reason,
        "recommendations": row.recommendations, "prescriptions": row.prescriptions,
        "origin": "doctor_entered" if row.recommendations is not None else "legacy_unclassified"}


def snapshot(assessment, can_review):
    return {"assessment_id": assessment.id, "state": assessment.review_state,
        "version": len(assessment.review_history), "can_review": can_review,
        "reviews": [review_data(row) for row in assessment.review_history]}


def validate_payload(payload):
    if set(payload) != {"expected_version", "decision", "clinical_notes", "recommendations", "prescriptions"}:
        raise BadRequest()
    if type(payload["expected_version"]) is not int or not 0 <= payload["expected_version"] < 100:
        raise BadRequest()
    if payload["decision"] not in ("approved", "returned_for_changes", "pending_review"):
        raise BadRequest()
    if not valid_text(payload["clinical_notes"], 4096, True):
        raise BadRequest()
    recs = payload["recommendations"]
    if not isinstance(recs, dict) or set(recs) != set(OUTPUT_TARGETS) or not all(valid_text(value, 2048, True) for value in recs.values()):
        raise BadRequest()
    prescriptions = payload["prescriptions"]
    if not isinstance(prescriptions, list) or len(prescriptions) > 10:
        raise BadRequest()
    for prescription in prescriptions:
        if not isinstance(prescription, dict) or set(prescription) != set(PRESCRIPTION_FIELDS):
            raise BadRequest()
        if not all(valid_text(prescription[key], 256, key != "instructions") for key in PRESCRIPTION_FIELDS):
            raise BadRequest()


@patients.get("/<int:patient_id>/assessments/<int:assessment_id>/reviews")
@roles_required("doctor")
def get_reviews(patient_id, assessment_id):
    assessment = record(patient_id, assessment_id)
    if request.args:
        raise BadRequest()
    return snapshot(assessment, review_permission(patient_id))


@patients.post("/<int:patient_id>/assessments/<int:assessment_id>/reviews")
@roles_required("doctor")
def save_review(patient_id, assessment_id):
    # Lock the grant before the assessment; revocation uses the same grant row.
    if not review_permission(patient_id, lock=True):
        raise Forbidden()
    assessment = record(patient_id, assessment_id, lock=True)
    if request.args:
        raise BadRequest()
    payload = json_object()
    validate_payload(payload)
    version = len(assessment.review_history)
    if version != payload["expected_version"]:
        raise Conflict()
    try:
        validate_review_transition(assessment.review_state, payload["decision"])
    except ValueError:
        raise Conflict() from None
    values = dict(assessment_id=assessment.id, sequence=version + 1, actor_user_id=g.current_user.id,
        from_state=assessment.review_state, to_state=payload["decision"], reason=payload["clinical_notes"],
        recommendations=payload["recommendations"], prescriptions=payload["prescriptions"], decided_at=utc_now())
    try:
        # Narrow service-owned Core insertion follows authorization and locking.
        # Ordinary ORM/bulk mutation guards remain enabled for review history.
        db.session.connection().execute(insert(AssessmentReview.__table__).values(**values))
        db.session.expire(assessment, ["review_history"])
        response = snapshot(assessment, True)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict() from None
    return response, 201
