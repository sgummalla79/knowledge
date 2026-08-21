"""profiles.is_system + seed Contributor/Viewer default profiles for every org

Every org previously got exactly one seeded, non-deletable profile (Admin, is_admin=true). Orgs
now get three: Admin (unchanged), Contributor (read/write on core content, no org-admin surface),
and Viewer (read-only across that same content) — see api/application/profile_service.py's
create_contributor_profile/create_viewer_profile and api/constants.py's
DEFAULT_CONTRIBUTOR_PERMISSIONS/DEFAULT_VIEWER_PERMISSIONS.

`is_system` generalizes the "protected" concept `is_admin` used to carry alone: it's a strict
superset (every is_admin profile is also is_system) that additionally covers Contributor/Viewer,
which need the same no-edit/no-delete protection without getting every permission. ProfileService
now checks is_system (not is_admin) before allowing update/delete — a behavior tightening for
Admin too, which could previously still be renamed; all three default profiles are now fully
locked, matching how the Settings > Profiles page already described them.

The permission string lists here are spelled out literally rather than imported from
api.constants — a migration's SQL should not depend on application code that can change
independently of this file's history (same rationale migration 0005 already documents).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Mirrors api/constants.py's DEFAULT_CONTRIBUTOR_PERMISSIONS as of this migration.
_CONTRIBUTOR_PERMISSIONS = (
    "documents:read", "documents:write", "categories:read", "categories:write",
    "shelves:read", "shelves:write", "tags:read", "tags:write", "embedding_models:read",
    "queries:execute",
)

# Mirrors api/constants.py's DEFAULT_VIEWER_PERMISSIONS as of this migration.
_VIEWER_PERMISSIONS = (
    "documents:read", "categories:read", "shelves:read", "tags:read", "embedding_models:read",
    "queries:execute",
)


def _permission_values_sql(permissions: tuple[str, ...]) -> str:
    return ", ".join(f"('{permission}')" for permission in permissions)


def upgrade():
    op.add_column("profiles", sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()))
    op.execute("update profiles set is_system = true where is_admin = true")

    op.execute(
        """
        insert into profiles (id, org_id, name, description, is_admin, is_system, created_at, last_modified_at)
        select gen_random_uuid(), o.id, 'Contributor',
               'Read/write access to documents, categories, shelves, and tags.', false, true, now(), now()
        from organizations o
        where not exists (select 1 from profiles p where p.org_id = o.id and p.name = 'Contributor')
        """
    )
    op.execute(
        f"""
        insert into profile_permissions (profile_id, permission, granted_at)
        select p.id, perms.permission, now()
        from profiles p
        cross join (values {_permission_values_sql(_CONTRIBUTOR_PERMISSIONS)}) as perms(permission)
        where p.name = 'Contributor' and p.is_system = true
          and not exists (
            select 1 from profile_permissions pp where pp.profile_id = p.id and pp.permission = perms.permission
          )
        """
    )

    op.execute(
        """
        insert into profiles (id, org_id, name, description, is_admin, is_system, created_at, last_modified_at)
        select gen_random_uuid(), o.id, 'Viewer',
               'Read-only access to documents, categories, shelves, and tags.', false, true, now(), now()
        from organizations o
        where not exists (select 1 from profiles p where p.org_id = o.id and p.name = 'Viewer')
        """
    )
    op.execute(
        f"""
        insert into profile_permissions (profile_id, permission, granted_at)
        select p.id, perms.permission, now()
        from profiles p
        cross join (values {_permission_values_sql(_VIEWER_PERMISSIONS)}) as perms(permission)
        where p.name = 'Viewer' and p.is_system = true
          and not exists (
            select 1 from profile_permissions pp where pp.profile_id = p.id and pp.permission = perms.permission
          )
        """
    )


def downgrade():
    op.execute("delete from profiles where name in ('Contributor', 'Viewer') and is_system = true")
    op.drop_column("profiles", "is_system")
