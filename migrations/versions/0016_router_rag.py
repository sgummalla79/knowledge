"""router RAG: description_embedding on libraries + router_settings table

Adds a cached embedding of each library's `description` (nullable — a library with no
description, or created before an embedding provider was ever active, simply has none) so a
query with no library_id can be routed to the most relevant library/libraries by cosine
similarity, instead of the caller always supplying an explicit library_id. Deliberately
dimensionless (`Vector()`, no fixed N and no HNSW index), unlike chunks.embedding: library counts
are small for this single-user local tool, so a sequential `ORDER BY ... <=> :query` scan is
trivial, and the "never compare vectors of different dims/semantics" invariant is enforced in
application code instead (every write nulls-then-recomputes atomically — see
EmbeddingProviderConfigService._resync_library_description_embeddings and
LibraryService._sync_description_embedding).

router_settings mirrors search_settings' shape: a single global row (top_n libraries to route to,
min_similarity threshold), absent row is not an error (RouterSettingsService fills in defaults).

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-09

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("libraries", sa.Column("description_embedding", Vector(), nullable=True))

    op.create_table(
        "router_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("top_n", sa.Integer, nullable=False),
        sa.Column("min_similarity", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("router_settings")
    op.drop_column("libraries", "description_embedding")
