"""embedding_settings.dimensions: data-driven vector dimension per configured model

Adds embedding_settings.dimensions so the (provider, model) -> dimension mapping is a user-
supplied value captured at PUT /embedding-settings time (verified live against the actual
provider response), instead of a static lookup table in app/constants.py. This is what lets a
caller configure any embeddings model/vendor, not just the ones the old whitelist enumerated —
see app/application/embedding_settings_service.py / embedding_choice_validation.py.

The single possible existing row is backfilled to EMBEDDING_DIM (768) since every row at this
point is already guaranteed 768-dim (migration 0007's cutover forced any incompatible provider
back to the 768-dim Ollama default).

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("embedding_settings", sa.Column("dimensions", sa.Integer, nullable=True))
    op.execute("UPDATE embedding_settings SET dimensions = 768 WHERE dimensions IS NULL")
    op.alter_column("embedding_settings", "dimensions", nullable=False)


def downgrade():
    op.drop_column("embedding_settings", "dimensions")
