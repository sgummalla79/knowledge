"""hybrid search: generated content_tsv column + GIN index on chunks, search_settings table

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # Generated column: Postgres keeps this in sync on every insert/update to `content`, so no
    # application code is ever responsible for writing it — no dense/sparse drift is possible.
    op.add_column(
        "chunks",
        sa.Column(
            "content_tsv",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
    )
    op.execute("CREATE INDEX ix_chunks_content_tsv_gin ON chunks USING gin (content_tsv)")

    op.create_table(
        "search_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rerank_enabled", sa.Boolean, nullable=False),
        sa.Column("rerank_provider", sa.String, nullable=False),
        sa.Column("rerank_model", sa.String, nullable=False),
        sa.Column("dense_k", sa.Integer, nullable=False),
        sa.Column("sparse_k", sa.Integer, nullable=False),
        sa.Column("rerank_candidates", sa.Integer, nullable=False),
        sa.Column("rrf_k", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("search_settings")
    op.execute("DROP INDEX IF EXISTS ix_chunks_content_tsv_gin")
    op.drop_column("chunks", "content_tsv")
