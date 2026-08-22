"""add organizations.description

A nullable free-text field for the org's General Settings page — additive, matches the
`description` column convention already used on categories/shelves/sources (see migration 0001).
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("organizations", sa.Column("description", sa.String, nullable=True))


def downgrade():
    op.drop_column("organizations", "description")
