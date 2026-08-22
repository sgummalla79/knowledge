"""personal_access_tokens: self-service, per-user API keys

Replaces the api_key Connected Applications method removed in migration 0010. A user creates a
token for themselves, in whichever org is currently active — token.org_id is fixed at creation,
same per-request-org model every other credential in this app already uses. At request time, the
token resolves to (identity_id, org_id) and permissions are resolved fresh via
PermissionService.resolve_permissions — the exact function the oauth_client_credentials JWT path
already calls, so a token's authority is always that identity's *current* profile in that org, not
anything baked into the token itself.

No revoked_at and no rotation, unlike Application credentials — deleting the row is the only
lifecycle-ending action (self-service "add/delete", not admin-managed "revoke then delete").
No api_access column either: unlike an Application (which might be MCP-only), a personal API key's
whole purpose is REST access, so that's unconditional; mcp_access stays an opt-in channel flag for
also reaching MCP tools, same concept applications.mcp_access already has.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "personal_access_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("identity_id", UUID(as_uuid=True), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("token_hash", sa.String, nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(12), nullable=False),
        sa.Column("mcp_access", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_personal_access_tokens_token_hash", "personal_access_tokens", ["token_hash"])
    op.create_index("ix_personal_access_tokens_identity_id", "personal_access_tokens", ["identity_id"])

    op.execute("alter table personal_access_tokens enable row level security")
    op.execute(
        "create policy tenant_isolation on personal_access_tokens using (org_id = current_setting('app.org_id')::uuid)"
    )


def downgrade():
    op.execute("drop policy tenant_isolation on personal_access_tokens")
    op.drop_table("personal_access_tokens")
