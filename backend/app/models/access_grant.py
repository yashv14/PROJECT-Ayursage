"""Explicit assessment-read grants; consent references are operator attestations."""
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.app.database import db


class GrantAdministrator(db.Model):
    __tablename__ = "grant_administrators"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    # Explicit local operator provisioning, never public role selection.
    authorized_at: Mapped[datetime] = mapped_column()


class PatientDoctorGrant(db.Model):
    __tablename__ = "patient_doctor_grants"
    __table_args__ = (
        UniqueConstraint("patient_id", "doctor_user_id", "active_slot", name="uq_grant_active_pair"),
        UniqueConstraint("patient_id", "doctor_user_id", "consent_reference", name="uq_grant_consent_pair"),
        CheckConstraint("scope = 'assessment_read'", name="ck_grant_scope"),
        CheckConstraint("expires_at > issued_at", name="ck_grant_expiry"),
        CheckConstraint("active_slot IS NULL OR active_slot = 1", name="ck_grant_slot"),
        CheckConstraint("length(trim(consent_reference)) > 0", name="ck_grant_consent"),
        CheckConstraint(
            "(status = 'issued' AND revoked_by_user_id IS NULL AND revoked_at IS NULL) OR "
            "(status = 'revoked' AND revoked_by_user_id IS NOT NULL AND revoked_at IS NOT NULL "
            "AND revoked_at >= issued_at AND active_slot IS NULL)", name="ck_grant_revocation",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    doctor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    consent_owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    consent_reference: Mapped[str] = mapped_column(String(256))
    issuer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scope: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    issued_at: Mapped[datetime] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column(index=True)
    revoked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revoked_at: Mapped[datetime | None] = mapped_column()
    # NULL permits multiple historical rows on both SQLite and MySQL.
    active_slot: Mapped[int | None] = mapped_column()


@event.listens_for(Session, "before_flush")
def preserve_grant_history(session, _context, _instances):
    # Application services use narrowly conditional Core updates for revocation and
    # retiring an expired slot. Ordinary ORM edits/deletes cannot rewrite history.
    if any(isinstance(row, PatientDoctorGrant) for row in session.deleted):
        raise ValueError("Grant history cannot be deleted")
    if any(isinstance(row, PatientDoctorGrant) and session.is_modified(row, include_collections=False)
           for row in session.dirty):
        raise ValueError("Grant history cannot be edited")


@event.listens_for(Session, "do_orm_execute")
def block_grant_bulk_changes(execution):
    if getattr(getattr(execution.statement, "table", None), "name", None) == "patient_doctor_grants":
        if execution.is_update or execution.is_delete:
            raise ValueError("Grant history changes require the grant service")
