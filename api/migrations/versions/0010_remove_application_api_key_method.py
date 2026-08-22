"""Remove api_key as a Connected Applications auth method

API keys move to a new, separate personal-access-token feature (migration 0011) — self-service,
created by a user for themselves, inheriting that user's own profile permissions, rather than an
admin-created org-level Application with its own hand-picked scope list and a synthetic,
unusable-for-login service identity. Connected Applications keeps only the two OAuth methods
(oauth_client_credentials, oauth_authorization_code) for real third-party integrations.

Deletes any existing auth_method='api_key' applications (cascades to application_api_keys/
application_scopes via their existing FKs; leaves the synthetic service identity/org_member rows
orphaned the same way a normal ApplicationService.delete() already does today — pre-existing
behavior, not something this migration changes) and drops the two tables that only ever backed
that method. Pre-release work (releases/v3-multi-tenant-data-model) — no real prod data.

Deliberately leaves 'api_key' in the application_auth_method Postgres enum: dropping an enum value
requires recreating the whole type (ALTER TYPE ... DROP VALUE isn't supported), and an unused value
is harmless — application code no longer has any path that produces or accepts it.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-21

"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("delete from applications where auth_method = 'api_key'")

    op.execute("drop policy tenant_isolation on application_api_keys")
    op.drop_table("application_api_keys")

    op.execute("drop policy tenant_isolation on application_scopes")
    op.drop_table("application_scopes")


def downgrade():
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import UUID

    op.create_table(
        "application_scopes",
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("application_id", "scope"),
    )
    op.execute("alter table application_scopes enable row level security")
    op.execute(
        """
        create policy tenant_isolation on application_scopes using (
          exists (select 1 from applications a where a.id = application_id and a.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )

    op.create_table(
        "application_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("key_hash", sa.String, nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_application_api_keys_key_hash", "application_api_keys", ["key_hash"])
    op.execute("alter table application_api_keys enable row level security")
    op.execute(
        """
        create policy tenant_isolation on application_api_keys using (
          exists (select 1 from applications a where a.id = application_id and a.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )
