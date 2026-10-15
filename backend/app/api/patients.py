"""Owner patient APIs and explicitly granted doctor assessment reads."""

from flask import Blueprint, current_app, g, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from backend.app.auth.security import roles_required, require_patient_owner
from backend.app.auth.grants import assessment_read_patient, authorized_patient_page
from backend.app.database import db
from backend.app.models import Patient, ClinicalAssessment
from .assessment_validation import json_object, assessment_payload


patients = Blueprint("patients", __name__, url_prefix="/patients")


@patients.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def owned_patient(patient_id):
    # Filter before reading records: missing and another owner's ID both return 404.
    if not 1 <= patient_id <= 2147483647:
        raise NotFound()
    patient = db.session.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.owner_user_id == g.current_user.id,
    ))
    if patient is None:
        raise NotFound()
    require_patient_owner(patient)
    return patient


def patient_data(patient):
    return {"id": patient.id, "owner_user_id": patient.owner_user_id}


def assessment_data(assessment):
    return {
        "id": assessment.id, "patient_id": assessment.patient_id,
        "recorded_by_user_id": assessment.recorded_by_user_id,
        "created_at": assessment.created_at.isoformat(),
        "inputs": assessment.inputs, "notes": assessment.notes,
    }


def readable_patient(patient_id):
    if g.current_user.role.code == "patient":
        return owned_patient(patient_id)
    return assessment_read_patient(patient_id)


@patients.get("/authorized")
@roles_required("doctor")
def authorized_patients():
    if set(request.args) - {"after_id"} or len(request.args.getlist("after_id")) > 1:
        raise BadRequest()
    try:
        after_id = int(request.args.get("after_id", "0"))
    except ValueError:
        raise BadRequest() from None
    if not 0 <= after_id <= 2147483647:
        raise BadRequest()
    return authorized_patient_page(after_id)


@patients.post("")
@roles_required("patient")
def create_patient():
    if json_object():
        raise BadRequest()
    existing = db.session.scalar(select(Patient.id).where(Patient.owner_user_id == g.current_user.id))
    if existing is not None:
        raise Conflict()
    patient = Patient(owner_user_id=g.current_user.id)
    db.session.add(patient)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict() from None
    return {"patient": patient_data(patient)}, 201


@patients.get("/me")
@roles_required("patient")
def my_patient():
    patient = db.session.scalar(select(Patient).where(Patient.owner_user_id == g.current_user.id))
    if patient is None:
        raise NotFound()
    require_patient_owner(patient)
    return {"patient": patient_data(patient)}


@patients.get("/<int:patient_id>")
@roles_required("patient")
def get_patient(patient_id):
    return {"patient": patient_data(owned_patient(patient_id))}


@patients.post("/<int:patient_id>/assessments")
@roles_required("patient")
def create_assessment(patient_id):
    patient = owned_patient(patient_id)
    inputs, notes, predict = assessment_payload()
    prediction = None
    if predict:
        # Owner checks and structural validation precede model work. Requests
        # never load a model. Failure occurs before constructing/persisting a row.
        prediction = current_app.extensions["v17"].predict(inputs)
    assessment = ClinicalAssessment(
        patient_id=patient.id, recorded_by_user_id=g.current_user.id,
        inputs=inputs, notes=notes,
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.refresh(assessment)
    # Snapshot generated values and JSON data before commit expires ORM attributes.
    response = {"assessment": assessment_data(assessment)}
    if prediction is not None:
        # Current schema supports inputs/notes only; never store labels in notes
        # or inputs, and never write a review decision or prescription here.
        response["prediction"] = prediction
    db.session.commit()
    return response, 201


@patients.get("/<int:patient_id>/assessments")
@roles_required("patient", "doctor")
def list_assessments(patient_id):
    patient = readable_patient(patient_id)
    if set(request.args) - {"limit", "after_id"} or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise BadRequest()
    try:
        limit = int(request.args.get("limit", "20"))
        after_id = int(request.args.get("after_id", "0"))
    except ValueError:
        raise BadRequest() from None
    if not 1 <= limit <= 100 or not 0 <= after_id <= 2147483647:
        raise BadRequest()
    rows = db.session.scalars(select(ClinicalAssessment).where(
        ClinicalAssessment.patient_id == patient.id, ClinicalAssessment.id > after_id,
    ).order_by(ClinicalAssessment.id).limit(limit + 1)).all()
    page = rows[:limit]
    return {
        "assessments": [assessment_data(row) for row in page],
        "next_after_id": page[-1].id if len(rows) > limit else None,
    }


@patients.get("/<int:patient_id>/assessments/<int:assessment_id>")
@roles_required("patient", "doctor")
def get_assessment(patient_id, assessment_id):
    patient = readable_patient(patient_id)
    if not 1 <= assessment_id <= 2147483647:
        raise NotFound()
    assessment = db.session.scalar(select(ClinicalAssessment).where(
        ClinicalAssessment.id == assessment_id, ClinicalAssessment.patient_id == patient.id,
    ))
    if assessment is None:
        raise NotFound()
    return {"assessment": assessment_data(assessment)}
