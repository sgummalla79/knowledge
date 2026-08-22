"""connected applications: data model + headless API key auth (phase 1 of 5)

Org-scoped "connected applications" so an org admin can grant a machine caller (MCP client,
external integration) scoped API access without an active login session. This migration lays
down the full application_auth_method enum (api_key/oauth_client_credentials/
oauth_authorization_code/certificate) up front, even though only the api_key method has a
matching table (application_api_keys) and service-layer support today — the column's shape is
already fully decided (see the approved plan this feature follows), and extending a Postgres ENUM
after the fact is enough friction that it's simpler to declare all 4 values now. Later phases add
application_oauth_clients, authorization_codes, refresh_tokens, and application_certificates in
their own migrations rather than growing this one, so each phase lands its schema alongside the
code that actually uses it.

`applications.auth_method` is immutable after creation (enforced in ApplicationService, not the
DB) — one application always has exactly one credential-method row.

Every application gets a synthetic, unusable-for-login `identities` row (service_identity_id) plus
an `org_members` admin row for it — the same pattern every other created_by/owner_id-style FK in
this schema already assumes a real identities.id exists (see ApplicationService.create). Its real
authority is bounded by application_scopes, checked by require_scope() before any role-based route
logic runs.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-19

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

application_auth_method = ENUM(
    "api_key",
    "oauth_client_credentials",
    "oauth_authorization_code",
    "certificate",
    name="application_auth_method",
    create_type=False,
)
application_status = ENUM("active", "revoked", name="application_status", create_type=False)

_ALL_ENUMS = (application_auth_method, application_status)


def upgrade():
    bind = op.get_bind()
    for enum in _ALL_ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("auth_method", application_auth_method, nullable=False),
        sa.Column("status", application_status, nullable=False, server_default="active"),
        sa.Column("service_identity_id", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("last_modified_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_applications_org_id_name"),
    )
    op.create_index("ix_applications_org_id", "applications", ["org_id"])

    op.create_table(
        "application_scopes",
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("application_id", "scope"),
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

    # ── Row-level security (matches migration 0001's convention — inert until a restricted DB
    # role exists, see that migration's docstring) ─────────────────────────────────────────────
    op.execute("alter table applications enable row level security")
    op.execute("create policy tenant_isolation on applications using (org_id = current_setting('app.org_id')::uuid)")

    op.execute("alter table application_scopes enable row level security")
    op.execute(
        """
        create policy tenant_isolation on application_scopes using (
          exists (select 1 from applications a where a.id = application_id and a.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )

    op.execute("alter table application_api_keys enable row level security")
    op.execute(
        """
        create policy tenant_isolation on application_api_keys using (
          exists (select 1 from applications a where a.id = application_id and a.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )


def downgrade():
    op.execute("drop policy tenant_isolation on application_api_keys")
    op.execute("drop policy tenant_isolation on application_scopes")
    op.execute("drop policy tenant_isolation on applications")

    op.drop_table("application_api_keys")
    op.drop_table("application_scopes")
    op.drop_table("applications")

    bind = op.get_bind()
    for enum in reversed(_ALL_ENUMS):
        enum.drop(bind, checkfirst=True)
