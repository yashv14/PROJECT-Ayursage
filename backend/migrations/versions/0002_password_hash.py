"""Add password hashes; legacy accounts remain unable to log in."""

from alembic import op
import sqlalchemy as sa

revision = "0002_password_hash"
down_revision = "0001_database_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(512), nullable=True))


def downgrade():
    op.drop_column("users", "password_hash")
