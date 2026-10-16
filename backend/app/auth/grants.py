"""Assessment-read authorization only; no profile, write or review privileges."""
from datetime import datetime, timedelta, timezone

from flask import g
from sqlalchemy import select
from werkzeug.exceptions import Forbidden

from backend.app.database import db
from backend.app.models import GrantAdministrator, PatientDoctorGrant, Patient


def utc_now():
    # UTC stored without timezone for consistent SQLite/MySQL DateTime semantics.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def is_grant_administrator(user):
    return user.role.code == "admin" and db.session.scalar(
        select(GrantAdministrator.user_id).where(GrantAdministrator.user_id == user.id)) is not None


def require_grant_administrator():
    if not is_grant_administrator(g.current_user):
        raise Forbidden()


def assessment_read_grants(now):
    """One shared, doctor-scoped query for both directory and individual reads."""
    return select(
        Patient.id.label("patient_id"), PatientDoctorGrant.issued_at, PatientDoctorGrant.expires_at,
        PatientDoctorGrant.consent_reference, PatientDoctorGrant.id.label("grant_id"), PatientDoctorGrant.allow_review,
    ).join(PatientDoctorGrant, PatientDoctorGrant.patient_id == Patient.id).where(
        PatientDoctorGrant.doctor_user_id == g.current_user.id,
        PatientDoctorGrant.consent_owner_user_id == Patient.owner_user_id,
        PatientDoctorGrant.scope == "assessment_read",
        PatientDoctorGrant.status == "issued", PatientDoctorGrant.active_slot == 1,
        PatientDoctorGrant.revoked_at.is_(None), PatientDoctorGrant.revoked_by_user_id.is_(None),
        PatientDoctorGrant.issued_at <= now, PatientDoctorGrant.expires_at > now,
    )


def valid_grant_details(row):
    # Preserve exact Python timedelta and whitespace semantics on SQLite/MySQL.
    return row.expires_at - row.issued_at == timedelta(days=30) and bool(row.consent_reference.strip())


def doctor_has_patient_grant(patient):
    if g.current_user.role.code != "doctor":
        return False
    # Scalar rows re-read revocation; no identity-map authorization cache.
    rows = db.session.execute(assessment_read_grants(utc_now()).where(Patient.id == patient.id)).all()
    return any(valid_grant_details(row) for row in rows)


def authorized_patient_page(after_id):
    if g.current_user.role.code != "doctor":
        raise Forbidden()
    query = assessment_read_grants(utc_now()).where(Patient.id > after_id).order_by(
        Patient.id, PatientDoctorGrant.id,
    ).execution_options(yield_per=20)
    ids = []
    # Stream bounded batches and retain at most 21 distinct IDs. Exact-duration
    # validation is shared with assessment reads, without dialect-specific date SQL.
    with db.session.execute(query) as rows:
        for row in rows:
            if valid_grant_details(row) and (not ids or ids[-1] != row.patient_id):
                ids.append(row.patient_id)
                if len(ids) == 21:
                    break
    return {"patients": [{"id": value} for value in ids[:20]],
            "next_after_id": ids[19] if len(ids) > 20 else None}


def assessment_read_patient(patient_id):
    if not 1 <= patient_id <= 2147483647:
        raise Forbidden()
    patient = db.session.scalar(select(Patient).where(Patient.id == patient_id))
    if patient is None or not doctor_has_patient_grant(patient):
        raise Forbidden()
    return patient
