"""Issued report metadata only; private PDF bytes live outside the database."""
from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, Session, mapped_column
from backend.app.database import db


class ClinicalReport(db.Model):
    __tablename__ = 'clinical_reports'
    __table_args__ = (
        UniqueConstraint('assessment_id', name='uq_report_assessment'),
        UniqueConstraint('review_id', name='uq_report_review'),
        CheckConstraint('version = 1', name='ck_report_version'),
        CheckConstraint('byte_length > 0', name='ck_report_length'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey('clinical_assessments.id', ondelete='RESTRICT'))
    review_id: Mapped[int] = mapped_column(ForeignKey('assessment_reviews.id', ondelete='RESTRICT'))
    issued_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    version: Mapped[int] = mapped_column()
    object_key: Mapped[str] = mapped_column(String(80), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    byte_length: Mapped[int] = mapped_column()
    issued_at: Mapped[datetime] = mapped_column()


@event.listens_for(Session, 'before_flush')
def immutable_reports(session, _context, _instances):
    if any(isinstance(row, ClinicalReport) for row in session.new | session.deleted):
        raise ValueError('Report writes require the report service')
    if any(isinstance(row, ClinicalReport) and session.is_modified(row, include_collections=False) for row in session.dirty):
        raise ValueError('Issued reports are immutable')


@event.listens_for(Session, 'do_orm_execute')
def block_report_dml(execution):
    if getattr(getattr(execution.statement, 'table', None), 'name', None) == 'clinical_reports':
        if execution.is_insert or execution.is_update or execution.is_delete:
            raise ValueError('Issued reports are service-owned and immutable')
