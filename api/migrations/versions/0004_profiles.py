"""profiles: org-scoped, reusable read/write permission bundles

Introduces `profiles` (a named bundle of per-object-type read/write grants, e.g. "Admin",
"Read-only Analyst") and `profile_permissions` (the grants themselves). This is the foundation for
replacing `org_members.role` — done in the next migration (0005), once every place that creates an
`org_members` row has been updated to assign a profile instead — so that migration isn't blocked
mid-way through app code needing both to exist simultaneously.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-19

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_profiles_org_id_name"),
    )
    op.create_index("ix_profiles_org_id", "profiles", ["org_id"])

    op.create_table(
        "profile_permissions",
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission", sa.String, nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", "permission"),
    )

    op.execute("alter table profiles enable row level security")
    op.execute("create policy tenant_isolation on profiles using (org_id = current_setting('app.org_id')::uuid)")

    op.execute("alter table profile_permissions enable row level security")
    op.execute(
        """
        create policy tenant_isolation on profile_permissions using (
          exists (select 1 from profiles p where p.id = profile_id and p.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )


def downgrade():
    op.execute("drop policy tenant_isolation on profile_permissions")
    op.execute("drop policy tenant_isolation on profiles")
    op.drop_table("profile_permissions")
    op.drop_table("profiles")
