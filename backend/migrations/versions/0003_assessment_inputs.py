"""Persist source-named clinical inputs without inventing legacy values."""

from alembic import op
import sqlalchemy as sa

revision = "0003_assessment_inputs"
down_revision = "0002_password_hash"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clinical_assessments", sa.Column("inputs", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    op.drop_column("clinical_assessments", "inputs")
