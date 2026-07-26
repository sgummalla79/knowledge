"""initial schema: libraries, documents, chunks + pgvector

Revision ID: 0001
Revises:
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    EMBEDDING_DIM,
)

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "libraries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("embedding_provider", sa.String, nullable=False, server_default=DEFAULT_EMBEDDING_PROVIDER),
        sa.Column("embedding_model", sa.String, nullable=False, server_default=DEFAULT_EMBEDDING_MODEL),
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default=str(DEFAULT_CHUNK_SIZE)),
        sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default=str(DEFAULT_CHUNK_OVERLAP)),
        sa.Column("document_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("library_id", UUID(as_uuid=True), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_filename", sa.String, nullable=False),
        sa.Column("file_type", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_library_id", "documents", ["library_id"])

    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("library_id", UUID(as_uuid=True), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.String, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_library_id", "chunks", ["library_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("libraries")
