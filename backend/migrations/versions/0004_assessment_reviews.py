"""Reserved append-only review history; no decision backfill or grants."""

from alembic import op
import sqlalchemy as sa

revision = "0004_assessment_reviews"
down_revision = "0003_assessment_inputs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assessment_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("clinical_assessments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("decided_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("assessment_id", "sequence", name="uq_review_assessment_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_review_sequence"),
        sa.CheckConstraint(
            "(from_state = 'pending_review' AND to_state IN ('approved', 'returned_for_changes')) "
            "OR (from_state = 'returned_for_changes' AND to_state = 'pending_review')",
            name="ck_review_transition",
        ),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_assessment_reviews_assessment_id", "assessment_reviews", ["assessment_id"])
    op.create_index("ix_assessment_reviews_actor_user_id", "assessment_reviews", ["actor_user_id"])


def downgrade():
    # Explicit migration only; dropping this table destroys review history.
    op.drop_table("assessment_reviews")
