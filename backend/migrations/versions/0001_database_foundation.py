"""Initial persistence schema and explicit roles. No accounts are seeded."""

from alembic import op
import sqlalchemy as sa


revision = "0001_database_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    options = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.CheckConstraint("code IN ('patient', 'doctor', 'admin')", name="ck_roles_code"),
        **options,
    )
    op.bulk_insert(roles, [{"id": 1, "code": "patient"}, {"id": 2, "code": "doctor"}, {"id": 3, "code": "admin"}])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        **options,
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True),
        **options,
    )
    op.create_table(
        "clinical_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("notes", sa.Text(), nullable=True),
        **options,
    )
    op.create_index("ix_clinical_assessments_patient_id", "clinical_assessments", ["patient_id"])
    op.create_index("ix_clinical_assessments_recorded_by_user_id", "clinical_assessments", ["recorded_by_user_id"])


def downgrade():
    op.drop_table("clinical_assessments")
    op.drop_table("patients")
    op.drop_table("users")
    op.drop_table("roles")
