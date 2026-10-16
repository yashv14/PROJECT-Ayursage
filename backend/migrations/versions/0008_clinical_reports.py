"""Approval-bound report metadata; no PDF bytes or clinical backfill."""
from alembic import op
import sqlalchemy as sa

revision = '0008_clinical_reports'
down_revision = '0007_clinical_review'
branch_labels = depends_on = None


def upgrade():
    op.create_table('clinical_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('clinical_assessments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('assessment_reviews.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('issued_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('object_key', sa.String(80), nullable=False, unique=True),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('snapshot_sha256', sa.String(64), nullable=False),
        sa.Column('byte_length', sa.Integer(), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('assessment_id', name='uq_report_assessment'),
        sa.UniqueConstraint('review_id', name='uq_report_review'),
        sa.CheckConstraint('version = 1', name='ck_report_version'),
        sa.CheckConstraint('byte_length > 0', name='ck_report_length'),
        mysql_engine='InnoDB', mysql_charset='utf8mb4')


def downgrade():
    # Operator must reconcile/delete private objects separately; this drops metadata.
    op.drop_table('clinical_reports')
