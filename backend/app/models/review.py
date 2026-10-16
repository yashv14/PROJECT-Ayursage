"""Immutable review history; only the authorized review API appends Core rows."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from backend.app.database import db


REVIEW_STATES = ("pending_review", "approved", "returned_for_changes")
REVIEW_TRANSITIONS = frozenset({
    ("pending_review", "approved"),
    ("pending_review", "returned_for_changes"),
    ("returned_for_changes", "pending_review"),
})


def validate_review_transition(from_state, to_state):
    """Validate reserved graph only; this does not grant review authorization."""
    if not isinstance(from_state, str) or not isinstance(to_state, str) or (from_state, to_state) not in REVIEW_TRANSITIONS:
        raise ValueError("Invalid review transition")


class ReviewWriteBlocked(ValueError):
    """Ordinary ORM insertion cannot bypass the authorized review service."""


class ReviewHistoryImmutable(ValueError):
    """Existing review decisions cannot be edited or deleted through ORM flush."""


class AssessmentReview(db.Model):
    __tablename__ = "assessment_reviews"
    __table_args__ = (
        UniqueConstraint("assessment_id", "sequence", name="uq_review_assessment_sequence"),
        CheckConstraint("sequence > 0", name="ck_review_sequence"),
        CheckConstraint(
            "(from_state = 'pending_review' AND to_state IN ('approved', 'returned_for_changes')) "
            "OR (from_state = 'returned_for_changes' AND to_state = 'pending_review')",
            name="ck_review_transition",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("clinical_assessments.id", ondelete="RESTRICT"), index=True)
    sequence: Mapped[int] = mapped_column()
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    decided_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    reason: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    prescriptions: Mapped[list | None] = mapped_column(JSON(none_as_null=True))
    assessment: Mapped["ClinicalAssessment"] = relationship(back_populates="review_history")
    actor: Mapped["User"] = relationship()


@event.listens_for(Session, "before_flush")
def protect_review_history(session, _context, _instances):
    # No role-only or caller-supplied authorization flag can bypass this gate.
    if any(isinstance(row, AssessmentReview) for row in session.new):
        raise ReviewWriteBlocked("Review writes require explicit grants and review policy")
    if any(isinstance(row, AssessmentReview) for row in session.deleted):
        raise ReviewHistoryImmutable("Review history is immutable")
    if any(isinstance(row, AssessmentReview) and session.is_modified(row, include_collections=False) for row in session.dirty):
        raise ReviewHistoryImmutable("Review history is immutable")


@event.listens_for(Session, "do_orm_execute")
def block_review_dml(execution):
    table = getattr(execution.statement, "table", None)
    if getattr(table, "name", None) == "assessment_reviews":
        if execution.is_insert:
            raise ReviewWriteBlocked("Review writes require explicit grants and review policy")
        if execution.is_update or execution.is_delete:
            raise ReviewHistoryImmutable("Review history is immutable")
