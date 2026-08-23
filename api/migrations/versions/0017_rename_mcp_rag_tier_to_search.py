"""Rename the MCP "rag" tier to "search"

The MCP tool tier named "rag" (mounted at /mcp/rag, gated by mcp_settings.rag_read_enabled) is
renamed to "search" throughout — route, DB column, permission-check tier string, tool module,
webui labels — for clarity: "RAG" is this whole app's general domain, so a tier literally named
"rag" read as ambiguous next to the other two tiers ("read"/"write"), especially once a user
pointed out the Settings > MCP page's "RAG (search)" label implied the URL should be /mcp/search
rather than /mcp/rag.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-23

"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("mcp_settings", "rag_read_enabled", new_column_name="search_read_enabled")


def downgrade():
    op.alter_column("mcp_settings", "search_read_enabled", new_column_name="rag_read_enabled")
