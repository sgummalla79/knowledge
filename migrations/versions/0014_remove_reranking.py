"""remove reranking: drop rerank_* columns from search_settings

Reranking has been fully removed (was already unreachable via the API — see
SUPPORTED_RERANK_MODELS_BY_PROVIDER, empty since the default embedding provider moved to keyless
local Ollama). Hybrid retrieval tuning (dense_k/sparse_k/rrf_k) is unaffected and stays on this
table.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("search_settings", "rerank_enabled")
    op.drop_column("search_settings", "rerank_provider")
    op.drop_column("search_settings", "rerank_model")
    op.drop_column("search_settings", "rerank_candidates")


def downgrade():
    op.add_column("search_settings", sa.Column("rerank_candidates", sa.Integer, nullable=False, server_default="20"))
    op.add_column("search_settings", sa.Column("rerank_model", sa.String, nullable=False, server_default="rerank-2"))
    op.add_column("search_settings", sa.Column("rerank_provider", sa.String, nullable=False, server_default="voyage"))
    op.add_column("search_settings", sa.Column("rerank_enabled", sa.Boolean, nullable=False, server_default=sa.false()))
