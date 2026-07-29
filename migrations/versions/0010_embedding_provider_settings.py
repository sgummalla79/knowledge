"""embedding_provider_settings: per-provider enable/disable toggle

Lets an admin deactivate a specific embedding provider adapter (voyage, ollama,
openai_compatible, ...) independently of the others — GET /embedding-options only lists enabled
providers, and PUT /embedding-settings rejects selecting a disabled one. Disabling a provider
never touches an already-saved embedding_settings row, so an in-use configuration keeps working
even if later disabled for *new* selection (see app/application/embedding_settings_service.py).

Rows are seeded (all providers enabled) idempotently at app startup by
bootstrap_embedding_provider_settings, not by this migration — this migration only creates the
table.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "embedding_provider_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String, nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("embedding_provider_settings")
