"""Persistence only. Role membership is not authentication or authorization."""

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from backend.app.database import db


ROLE_CODES = ("patient", "doctor", "admin", "receptionist")
MYSQL_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


class Role(db.Model):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("code IN ('patient', 'doctor', 'admin', 'receptionist')", name="ck_roles_code"),
        MYSQL_OPTIONS.copy(),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    users: Mapped[list["User"]] = relationship(back_populates="role", passive_deletes="all")


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = MYSQL_OPTIONS.copy()

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    # Legacy database rows remain valid but cannot authenticate without a hash.
    password_hash: Mapped[str | None] = mapped_column(String(512))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    role: Mapped[Role] = relationship(back_populates="users")
    patient: Mapped["Patient | None"] = relationship(back_populates="owner", passive_deletes="all")
    assessments: Mapped[list["ClinicalAssessment"]] = relationship(
        back_populates="recorded_by", passive_deletes="all"
    )


class Patient(db.Model):
    __tablename__ = "patients"
    __table_args__ = MYSQL_OPTIONS.copy()

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    owner: Mapped[User] = relationship(back_populates="patient")
    assessments: Mapped[list["ClinicalAssessment"]] = relationship(
        back_populates="patient", passive_deletes="all"
    )


class ClinicalAssessment(db.Model):
    __tablename__ = "clinical_assessments"
    __table_args__ = MYSQL_OPTIONS.copy()

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    recorded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    notes: Mapped[str | None] = mapped_column(Text)
    # Null preserves legacy manual records; new API assessments require all inputs.
    inputs: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    patient: Mapped[Patient] = relationship(back_populates="assessments")
    recorded_by: Mapped[User] = relationship(back_populates="assessments")
    review_history: Mapped[list["AssessmentReview"]] = relationship(
        back_populates="assessment", order_by="AssessmentReview.sequence", passive_deletes="all"
    )

    @property
    def review_state(self):
        # No prediction/review is implied by creating an assessment.
        state = "pending_review"
        for sequence, decision in enumerate(self.review_history, 1):
            if decision.sequence != sequence or decision.from_state != state:
                raise ValueError("Invalid review history")
            validate_review_transition(state, decision.to_state)
            state = decision.to_state
        return state


from .review import AssessmentReview, validate_review_transition  # noqa: E402,F401
from .access_grant import GrantAdministrator, PatientDoctorGrant  # noqa: E402,F401
from .appointment import Appointment, AppointmentEvent, AppointmentLock  # noqa: E402,F401
from .report import ClinicalReport  # noqa: E402,F401
