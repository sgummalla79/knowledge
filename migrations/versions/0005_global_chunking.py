"""move chunk_size/chunk_overlap to embedding_settings; drop per-library embedding overrides

Chunking and the embedding provider/model are now configured once, globally, in
embedding_settings — libraries no longer carry their own embedding_provider/embedding_model/
chunk_size/chunk_overlap (there was never a real use case for per-library overrides, and it just
meant the same thing could be set in two places).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 100
_DEFAULT_EMBEDDING_PROVIDER = "voyage"
_DEFAULT_EMBEDDING_MODEL = "voyage-3"


def upgrade():
    op.add_column(
        "embedding_settings",
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default=str(_DEFAULT_CHUNK_SIZE)),
    )
    op.add_column(
        "embedding_settings",
        sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default=str(_DEFAULT_CHUNK_OVERLAP)),
    )
    op.drop_column("libraries", "embedding_provider")
    op.drop_column("libraries", "embedding_model")
    op.drop_column("libraries", "chunk_size")
    op.drop_column("libraries", "chunk_overlap")


def downgrade():
    op.add_column(
        "libraries",
        sa.Column("embedding_provider", sa.String, nullable=False, server_default=_DEFAULT_EMBEDDING_PROVIDER),
    )
    op.add_column(
        "libraries",
        sa.Column("embedding_model", sa.String, nullable=False, server_default=_DEFAULT_EMBEDDING_MODEL),
    )
    op.add_column(
        "libraries",
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default=str(_DEFAULT_CHUNK_SIZE)),
    )
    op.add_column(
        "libraries",
        sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default=str(_DEFAULT_CHUNK_OVERLAP)),
    )
    op.drop_column("embedding_settings", "chunk_size")
    op.drop_column("embedding_settings", "chunk_overlap")
