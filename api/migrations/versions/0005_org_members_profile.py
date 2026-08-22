"""org_members: replace role with profile_id

Every place in application code that used to assign `role="admin"` now assigns an org's Admin
profile instead (see ProfileService.create_admin_profile / api/application/*.py). This migration
does the corresponding data move: for every org, ensure an Admin profile exists with every
OBJECT_PERMISSIONS entry granted, and back every `role='admin'` member onto it; for orgs with any
non-admin member, seed a "Member" profile (read everywhere, write on documents/categories/shelves/
tags — roughly what *any* member can already do today, since there is currently no write
restriction below admin) and back every non-admin member onto that, so no membership row is left
without a profile. Then `profile_id` is made NOT NULL, `role` is dropped, and the now-unused
`user_role` enum type is dropped. Also updates the `shelf_gated_read` RLS policy (still inert
today, see migration 0001's docstring) to check `profiles.is_admin` via a join instead of
`role = 'admin'`.

The permission string list here is spelled out literally (matching how migration 0001 spells out
enum values literally) rather than imported from api.constants.OBJECT_PERMISSIONS — a migration's
SQL should not depend on application code that can change independently of this file's history.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-19

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

user_role = ENUM("admin", "contributor", "viewer", name="user_role", create_type=False)

# Every OBJECT_PERMISSIONS entry, as of this migration — the Admin profile gets all of them.
_ADMIN_PERMISSIONS = (
    "org:write", "documents:read", "documents:write", "categories:read", "categories:write",
    "shelves:read", "shelves:write", "tags:read", "tags:write", "embedding_models:read",
    "embedding_models:write", "org_members:read", "org_members:write", "applications:read",
    "applications:write", "profiles:read", "profiles:write", "queries:execute",
)

# What a non-admin member could already do before this migration (any role could write
# documents/categories/shelves/tags; only admin-only routes were actually gated).
_MEMBER_PERMISSIONS = (
    "documents:read", "documents:write", "categories:read", "categories:write",
    "shelves:read", "shelves:write", "tags:read", "tags:write", "embedding_models:read",
    "org_members:read", "applications:read", "profiles:read", "queries:execute",
)


def _permission_values_sql(permissions: tuple[str, ...]) -> str:
    return ", ".join(f"('{permission}')" for permission in permissions)


def upgrade():
    op.add_column("org_members", sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id"), nullable=True))

    # 1. Ensure every org has an Admin profile, fully permissioned.
    op.execute(
        """
        insert into profiles (id, org_id, name, description, is_admin, created_at, last_modified_at)
        select gen_random_uuid(), o.id, 'Admin', 'Full access to every object.', true, now(), now()
        from organizations o
        where not exists (select 1 from profiles p where p.org_id = o.id and p.is_admin = true)
        """
    )
    op.execute(
        f"""
        insert into profile_permissions (profile_id, permission, granted_at)
        select p.id, perms.permission, now()
        from profiles p
        cross join (values {_permission_values_sql(_ADMIN_PERMISSIONS)}) as perms(permission)
        where p.is_admin = true
          and not exists (
            select 1 from profile_permissions pp where pp.profile_id = p.id and pp.permission = perms.permission
          )
        """
    )
    op.execute(
        """
        update org_members om
        set profile_id = p.id
        from profiles p
        where p.org_id = om.org_id and p.is_admin = true and om.role = 'admin'
        """
    )

    # 2. Seed a "Member" fallback profile for any org with a non-admin member, and back them onto it.
    op.execute(
        """
        insert into profiles (id, org_id, name, description, is_admin, created_at, last_modified_at)
        select gen_random_uuid(), o.id, 'Member',
               'Migrated from the old contributor/viewer roles — read access everywhere, write access to documents, categories, shelves, and tags.',
               false, now(), now()
        from organizations o
        where exists (select 1 from org_members om where om.org_id = o.id and om.role != 'admin')
          and not exists (select 1 from profiles p where p.org_id = o.id and p.name = 'Member')
        """
    )
    op.execute(
        f"""
        insert into profile_permissions (profile_id, permission, granted_at)
        select p.id, perms.permission, now()
        from profiles p
        cross join (values {_permission_values_sql(_MEMBER_PERMISSIONS)}) as perms(permission)
        where p.name = 'Member' and p.is_admin = false
          and not exists (
            select 1 from profile_permissions pp where pp.profile_id = p.id and pp.permission = perms.permission
          )
        """
    )
    op.execute(
        """
        update org_members om
        set profile_id = p.id
        from profiles p
        where p.org_id = om.org_id and p.name = 'Member' and p.is_admin = false
          and om.role != 'admin' and om.profile_id is null
        """
    )

    op.alter_column("org_members", "profile_id", nullable=False)

    # shelf_gated_read references org_members.role directly, so it must be dropped before the
    # column it depends on can be.
    op.execute("drop policy shelf_gated_read on documents")
    op.drop_column("org_members", "role")

    bind = op.get_bind()
    user_role.drop(bind, checkfirst=True)

    op.execute(
        """
        create policy shelf_gated_read on documents
          as restrictive
          for select using (
            exists (
              select 1 from org_members m
              join profiles p on p.id = m.profile_id
              where m.identity_id = current_setting('app.user_id')::uuid
                and m.org_id = current_setting('app.org_id')::uuid
                and p.is_admin = true
            )
            or exists (
              select 1 from document_shelves ds
              join user_shelf_access usa on usa.shelf_id = ds.shelf_id
              where ds.document_id = documents.id
                and usa.user_id = current_setting('app.user_id')::uuid
            )
          )
        """
    )


def downgrade():
    op.execute("drop policy shelf_gated_read on documents")
    op.execute(
        """
        create policy shelf_gated_read on documents
          as restrictive
          for select using (
            exists (
              select 1 from org_members m
              where m.identity_id = current_setting('app.user_id')::uuid
                and m.org_id = current_setting('app.org_id')::uuid
                and m.role = 'admin'
            )
            or exists (
              select 1 from document_shelves ds
              join user_shelf_access usa on usa.shelf_id = ds.shelf_id
              where ds.document_id = documents.id
                and usa.user_id = current_setting('app.user_id')::uuid
            )
          )
        """
    )

    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    op.add_column("org_members", sa.Column("role", user_role, nullable=True))
    op.execute(
        """
        update org_members om
        set role = case when p.is_admin then 'admin' else 'contributor' end
        from profiles p
        where p.id = om.profile_id
        """
    )
    op.alter_column("org_members", "role", nullable=False, server_default="viewer")
    op.drop_column("org_members", "profile_id")
