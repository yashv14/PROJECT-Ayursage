"""Consent-attested issuance and owner/authorized-administrator revocation."""
from datetime import timedelta

from flask import g
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from backend.app.auth.security import roles_required
from backend.app.auth.grants import utc_now, require_grant_administrator, is_grant_administrator
from backend.app.database import db
from backend.app.models import Patient, User, PatientDoctorGrant
from .patients import patients
from .assessment_validation import json_object, valid_text


def bounded_id(value):
    return type(value) is int and 1 <= value <= 2147483647


def grant_data(row):
    def timestamp(value):
        return value.isoformat() + "Z" if value else None
    return {"id": row.id, "patient_id": row.patient_id, "doctor_user_id": row.doctor_user_id,
        "scope": row.scope, "allow_review": row.allow_review,
        "status": "expired" if row.status == "issued" and row.expires_at <= utc_now() else row.status,
        "issuer_user_id": row.issuer_user_id, "consent_owner_user_id": row.consent_owner_user_id,
        "consent_reference": row.consent_reference, "issued_at": timestamp(row.issued_at),
        "expires_at": timestamp(row.expires_at), "revoked_by_user_id": row.revoked_by_user_id,
        "revoked_at": timestamp(row.revoked_at)}


@patients.post("/<int:patient_id>/doctor-access-grants")
@roles_required("admin")
def issue_grant(patient_id):
    require_grant_administrator()
    if not bounded_id(patient_id):
        raise NotFound()
    payload = json_object()
    if not {"doctor_user_id", "consent_reference"} <= set(payload) or set(payload) - {"doctor_user_id", "consent_reference", "allow_review"}:
        raise BadRequest()
    if type(payload.get("allow_review", False)) is not bool:
        raise BadRequest()
    doctor_id = payload["doctor_user_id"]
    reference = payload["consent_reference"]
    # Opaque reference only: no URL fetching, uploads or clinical text in audit.
    if not bounded_id(doctor_id) or not valid_text(reference, 256, nonblank=True) or any(ord(c) < 32 for c in reference):
        raise BadRequest()
    patient = db.session.scalar(select(Patient).where(Patient.id == patient_id).with_for_update())
    if patient is None:
        raise NotFound()
    doctor = db.session.get(User, doctor_id)
    if doctor is None or doctor.role.code != "doctor" or not doctor.password_hash:
        raise BadRequest()
    owner = db.session.get(User, patient.owner_user_id)
    if owner is None or owner.role.code != "patient":
        raise BadRequest()
    now = utc_now()
    table = PatientDoctorGrant.__table__
    # Free only expired slots, preserving issuance/consent history. Unique active
    # pair handles concurrent issuance on SQLite as well as MySQL.
    db.session.connection().execute(update(table).where(
        table.c.patient_id == patient_id, table.c.doctor_user_id == doctor_id,
        table.c.active_slot == 1, table.c.expires_at <= now,
    ).values(active_slot=None))
    row = PatientDoctorGrant(patient_id=patient.id, doctor_user_id=doctor.id,
        consent_owner_user_id=patient.owner_user_id, consent_reference=reference.strip(),
        issuer_user_id=g.current_user.id, scope="assessment_read", status="issued",
        issued_at=now, expires_at=now + timedelta(days=30), active_slot=1,
        allow_review=payload.get("allow_review", False))
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict() from None
    return {"grant": grant_data(row)}, 201


@patients.get("/<int:patient_id>/doctor-access-grants")
@roles_required("patient", "admin")
def list_grants(patient_id):
    if g.current_user.role.code == "admin":
        require_grant_administrator()
    if not bounded_id(patient_id):
        raise NotFound()
    query = select(Patient.id).where(Patient.id == patient_id)
    if g.current_user.role.code == "patient":
        query = query.where(Patient.owner_user_id == g.current_user.id)
    if db.session.scalar(query) is None:
        raise NotFound()
    # Reuse bounded pagination; no unbounded audit-history response.
    from flask import request
    if set(request.args) - {"after_id"} or len(request.args.getlist("after_id")) > 1:
        raise BadRequest()
    try:
        after_id = int(request.args.get("after_id", "0"))
    except ValueError:
        raise BadRequest() from None
    if not 0 <= after_id <= 2147483647:
        raise BadRequest()
    rows = db.session.scalars(select(PatientDoctorGrant).where(
        PatientDoctorGrant.patient_id == patient_id, PatientDoctorGrant.id > after_id,
    ).order_by(PatientDoctorGrant.id).limit(21).execution_options(populate_existing=True)).all()
    return {"grants": [grant_data(row) for row in rows[:20]],
            "next_after_id": rows[19].id if len(rows) > 20 else None}


@patients.post("/<int:patient_id>/doctor-access-grants/<int:grant_id>/revoke")
@roles_required("patient", "admin")
def revoke_grant(patient_id, grant_id):
    if g.current_user.role.code == "admin" and not is_grant_administrator(g.current_user):
        raise Forbidden()
    if not bounded_id(patient_id) or not bounded_id(grant_id):
        raise NotFound()
    query = select(Patient).where(Patient.id == patient_id)
    if g.current_user.role.code == "patient":
        query = query.where(Patient.owner_user_id == g.current_user.id)
    patient = db.session.scalar(query)
    if patient is None:
        raise NotFound()
    if json_object():
        raise BadRequest()
    row = db.session.scalar(select(PatientDoctorGrant).where(
        PatientDoctorGrant.id == grant_id, PatientDoctorGrant.patient_id == patient.id,
    ).execution_options(populate_existing=True))
    if row is None:
        raise NotFound()
    table = PatientDoctorGrant.__table__
    # First revoker wins; repeat requests preserve original actor/timestamp.
    db.session.connection().execute(update(table).where(
        table.c.id == grant_id, table.c.status == "issued",
    ).values(status="revoked", active_slot=None, revoked_at=utc_now(), revoked_by_user_id=g.current_user.id))
    db.session.commit()
    db.session.refresh(row)
    return {"grant": grant_data(row)}
