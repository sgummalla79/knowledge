"""per-provider embedding config: merge embedding_settings into embedding_provider_settings

Replaces the single global embedding_settings row (one active provider/model/api_key/base_url/
dimensions/chunk_size/chunk_overlap at a time, selected from a UI dropdown) with a config row per
known provider. embedding_provider_settings already had one row per provider (voyage/ollama/
openai_compatible) holding only an `enabled` toggle that gated whether a provider was *selectable*
in that dropdown (migration 0010) — this migration adds the connection/chunking columns to that
same table and repurposes `enabled` to mean "this is the one active provider actually used for
embedding", matching the app's still-global (not per-library) embedding model. Only one row may
have enabled=true at a time, now enforced by ix_embedding_provider_settings_single_enabled as well
as EmbeddingProviderConfigService.enable()/disable().

Data migration: whichever provider embedding_settings held (if any) becomes the sole enabled row,
carrying its config over; every other provider is left disabled — the app-level default changes
from "voyage/openai_compatible enabled, ollama disabled" (bootstrap_embedding_provider_settings)
to "every provider disabled" here too, since an admin must now explicitly configure + enable one
via its own dashboard page rather than picking from a dropdown that assumed something was already
selectable.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("embedding_provider_settings", sa.Column("model", sa.String, nullable=True))
    op.add_column("embedding_provider_settings", sa.Column("api_key", sa.String, nullable=True))
    op.add_column("embedding_provider_settings", sa.Column("base_url", sa.String, nullable=True))
    op.add_column("embedding_provider_settings", sa.Column("dimensions", sa.Integer, nullable=True))
    op.add_column("embedding_provider_settings", sa.Column("chunk_size", sa.Integer, nullable=True))
    op.add_column("embedding_provider_settings", sa.Column("chunk_overlap", sa.Integer, nullable=True))
    op.add_column(
        "embedding_provider_settings",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # The previously-active global config (if any) becomes that provider's row, and the sole
    # enabled one — every other provider's row (pre-existing from bootstrap, or about to be
    # created by it on next app start) is disabled regardless of its old selectable-in-dropdown
    # toggle value.
    op.execute("UPDATE embedding_provider_settings SET enabled = false")
    op.execute(
        """
        UPDATE embedding_provider_settings AS eps
        SET
            model = es.model,
            api_key = es.api_key,
            base_url = es.base_url,
            dimensions = es.dimensions,
            chunk_size = es.chunk_size,
            chunk_overlap = es.chunk_overlap,
            created_at = es.created_at,
            enabled = true
        FROM embedding_settings AS es
        WHERE eps.provider = es.provider
        """
    )
    # bootstrap_embedding_provider_settings only creates a row for a provider that doesn't
    # already have one — if embedding_settings' provider somehow predates its
    # embedding_provider_settings row (a database older than migration 0010), insert it directly
    # rather than silently losing the active configuration.
    op.execute(
        """
        INSERT INTO embedding_provider_settings
            (id, provider, enabled, model, api_key, base_url, dimensions, chunk_size, chunk_overlap, created_at, updated_at)
        SELECT gen_random_uuid(), es.provider, true, es.model, es.api_key, es.base_url, es.dimensions,
               es.chunk_size, es.chunk_overlap, es.created_at, es.updated_at
        FROM embedding_settings AS es
        WHERE NOT EXISTS (
            SELECT 1 FROM embedding_provider_settings AS eps WHERE eps.provider = es.provider
        )
        """
    )

    op.drop_table("embedding_settings")

    op.alter_column("embedding_provider_settings", "enabled", server_default=sa.false())
    op.create_index(
        "ix_embedding_provider_settings_single_enabled",
        "embedding_provider_settings",
        ["enabled"],
        unique=True,
        postgresql_where=sa.text("enabled IS TRUE"),
    )


def downgrade():
    op.drop_index("ix_embedding_provider_settings_single_enabled", table_name="embedding_provider_settings")
    op.alter_column("embedding_provider_settings", "enabled", server_default=sa.true())

    op.create_table(
        "embedding_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String, nullable=False),
        sa.Column("model", sa.String, nullable=False),
        sa.Column("api_key", sa.String, nullable=True),
        sa.Column("base_url", sa.String, nullable=True),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("chunk_size", sa.Integer, nullable=False),
        sa.Column("chunk_overlap", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        INSERT INTO embedding_settings
            (id, provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap, created_at, updated_at)
        SELECT gen_random_uuid(), provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap,
               created_at, updated_at
        FROM embedding_provider_settings
        WHERE enabled IS TRUE AND model IS NOT NULL
        """
    )

    op.drop_column("embedding_provider_settings", "created_at")
    op.drop_column("embedding_provider_settings", "chunk_overlap")
    op.drop_column("embedding_provider_settings", "chunk_size")
    op.drop_column("embedding_provider_settings", "dimensions")
    op.drop_column("embedding_provider_settings", "base_url")
    op.drop_column("embedding_provider_settings", "api_key")
    op.drop_column("embedding_provider_settings", "model")
