"""Explicit review consent and human-authored review content; no backfill decisions."""
from alembic import op
import sqlalchemy as sa

revision = "0007_clinical_review"
down_revision = "0006_receptionist_appointments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("patient_doctor_grants", sa.Column("allow_review", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("assessment_reviews", sa.Column("recommendations", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("assessment_reviews", sa.Column("prescriptions", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    # Explicit operator action: removing these columns loses human-authored content.
    op.drop_column("assessment_reviews", "prescriptions")
    op.drop_column("assessment_reviews", "recommendations")
    op.drop_column("patient_doctor_grants", "allow_review")
