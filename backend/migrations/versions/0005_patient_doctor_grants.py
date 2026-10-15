"""Explicit administrator permission and auditable 30-day assessment-read grants."""
from alembic import op
import sqlalchemy as sa

revision = "0005_patient_doctor_grants"
down_revision = "0004_assessment_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("grant_administrators",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("authorized_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4")
    op.create_table("patient_doctor_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("doctor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consent_owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consent_reference", sa.String(256), nullable=False),
        sa.Column("issuer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("active_slot", sa.Integer(), nullable=True),
        sa.UniqueConstraint("patient_id", "doctor_user_id", "active_slot", name="uq_grant_active_pair"),
        sa.UniqueConstraint("patient_id", "doctor_user_id", "consent_reference", name="uq_grant_consent_pair"),
        sa.CheckConstraint("scope = 'assessment_read'", name="ck_grant_scope"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_grant_expiry"),
        sa.CheckConstraint("active_slot IS NULL OR active_slot = 1", name="ck_grant_slot"),
        sa.CheckConstraint("length(trim(consent_reference)) > 0", name="ck_grant_consent"),
        sa.CheckConstraint("(status = 'issued' AND revoked_by_user_id IS NULL AND revoked_at IS NULL) OR "
            "(status = 'revoked' AND revoked_by_user_id IS NOT NULL AND revoked_at IS NOT NULL "
            "AND revoked_at >= issued_at AND active_slot IS NULL)", name="ck_grant_revocation"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4")
    for column in ("patient_id", "doctor_user_id", "expires_at"):
        op.create_index("ix_patient_doctor_grants_" + column, "patient_doctor_grants", [column])


def downgrade():
    op.drop_table("patient_doctor_grants")
    op.drop_table("grant_administrators")
