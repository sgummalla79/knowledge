"""MCP exposure: applications.mcp_access + org-level tool-tier activation (mcp_settings)

The api process is being exposed over MCP transport as three separate, non-overlapping tool
tiers (RAG / object-read / object-write — see api/mcp_server/). Two independent gates control access,
on top of the profile-based permission check every tool already performs per call:

- `applications.mcp_access`: whether a given connected application may reach MCP at all, uniform
  across all three auth methods (api_key/oauth_client_credentials/oauth_authorization_code) —
  deliberately not folded into APPLICATION_SCOPES (api_key-only) or OBJECT_PERMISSIONS (profile-
  based, per-identity) since it's a channel flag on the application itself, independent of both.
- `mcp_settings`: one row per org, three independent booleans, each gating whether that tool tier
  is reachable for the org at all regardless of any individual application's mcp_access or any
  identity's profile. Defaults to all-off — an org must explicitly opt in, same as this being a
  new access surface rather than something already implicitly trusted.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("mcp_access", sa.Boolean, nullable=False, server_default=sa.false()))

    op.create_table(
        "mcp_settings",
        sa.Column(
            "org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("rag_read_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("object_read_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("object_write_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column(
            "last_modified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.execute("alter table mcp_settings enable row level security")
    op.execute("create policy tenant_isolation on mcp_settings using (org_id = current_setting('app.org_id')::uuid)")

    # Every existing org's Admin profile needs the two new OBJECT_PERMISSIONS entries too — see
    # migration 0005's identical reasoning: ProfileService only ever applies OBJECT_PERMISSIONS to
    # a *newly created* Admin profile, so a profile seeded before this migration would otherwise
    # never gain access to the new mcp-settings route without this backfill.
    op.execute(
        """
        insert into profile_permissions (profile_id, permission, granted_at)
        select p.id, perms.permission, now()
        from profiles p
        cross join (values ('mcp_settings:read'), ('mcp_settings:write')) as perms(permission)
        where p.is_admin = true
          and not exists (
            select 1 from profile_permissions pp where pp.profile_id = p.id and pp.permission = perms.permission
          )
        """
    )


def downgrade():
    op.execute("delete from profile_permissions where permission in ('mcp_settings:read', 'mcp_settings:write')")
    op.execute("drop policy tenant_isolation on mcp_settings")
    op.drop_table("mcp_settings")
    op.drop_column("applications", "mcp_access")
