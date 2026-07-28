"""local embeddings: nullable chunks.embedding_new (768-dim), embedding_settings.api_key/base_url

Schema-only step 1 of 2 for switching the default embedding provider to a local Ollama model
(nomic-embed-text, 768-dim), which is incompatible with the existing 1024-dim chunks.embedding
column. This migration only adds nullable columns — no data movement, safe on prod at any time.

Existing embedding data (if any) must be backfilled into embedding_new via
`python -m app.cli reembed-chunks` BEFORE migration 0007 (which drops the old column and cuts
over) is ever applied. See migration 0007's docstring for the full rollout runbook.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from app.constants import EMBEDDING_DIM

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chunks", sa.Column("embedding_new", Vector(EMBEDDING_DIM), nullable=True))
    op.alter_column("embedding_settings", "api_key", nullable=True)
    op.add_column("embedding_settings", sa.Column("base_url", sa.String, nullable=True))


def downgrade():
    op.drop_column("embedding_settings", "base_url")
    # Only succeeds if no row currently has a NULL api_key (e.g. an Ollama row seeded by
    # bootstrap_default_embedding_settings) — provided for symmetry, not expected to run on prod.
    op.alter_column("embedding_settings", "api_key", nullable=False)
    op.drop_column("chunks", "embedding_new")
