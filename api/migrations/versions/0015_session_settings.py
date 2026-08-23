"""Org-configurable session inactivity timeout (session_settings)

Browser (cookie) sessions had no inactivity timeout — only a 31-day *absolute* expiry from
Flask's untouched PERMANENT_SESSION_LIFETIME default, and identities.last_active_at (added in
migration 0001) was dead code, never written anywhere. This adds a real one, org-admin
configurable: one row per org, default 120 minutes, adjustable 15-1440 (enforced at the API
schema layer, api/presentation/schemas.py's SessionSettingsUpdateRequest — see
api/presentation/web/session_guard.py for where the actual timeout check runs).

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-22

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session_settings",
        sa.Column(
            "org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("inactivity_timeout_minutes", sa.Integer, nullable=False, server_default="120"),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column(
            "last_modified_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.execute("alter table session_settings enable row level security")
    op.execute(
        "create policy tenant_isolation on session_settings using (org_id = current_setting('app.org_id')::uuid)"
    )

    # Every existing org's Admin profile needs the two new OBJECT_PERMISSIONS entries too — see
    # migration 0008's identical reasoning: ProfileService only ever applies OBJECT_PERMISSIONS to
    # a *newly created* Admin profile, so a profile seeded before this migration would otherwise
    # never gain access to the new session-settings route without this backfill.
    op.execute(
        """
        insert into profile_permissions (profile_id, permission, granted_at)
        select p.id, perms.permission, now()
        from profiles p
        cross join (values ('session_settings:read'), ('session_settings:write')) as perms(permission)
        where p.is_admin = true
          and not exists (
            select 1 from profile_permissions pp where pp.profile_id = p.id and pp.permission = perms.permission
          )
        """
    )


def downgrade():
    op.execute("delete from profile_permissions where permission in ('session_settings:read', 'session_settings:write')")
    op.execute("drop policy tenant_isolation on session_settings")
    op.drop_table("session_settings")
