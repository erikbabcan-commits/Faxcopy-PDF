"""Account for previews; legacy files require read-only reconciliation before release."""
from alembic import op
import sqlalchemy as sa

revision = "20261024_preview_bytes"
down_revision = "20f0e9f68eac"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("jobs", sa.Column("preview_size_bytes", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    op.drop_column("jobs", "preview_size_bytes")
