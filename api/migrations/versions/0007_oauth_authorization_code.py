"""connected applications: oauth_authorization_code + PKCE (phase C of the connected-applications
feature)

Adds the user-delegated counterpart to phase B's client_credentials: an org member completes a
browser consent screen and the resulting token acts as them, decided fresh each time rather than
pre-picked by an admin. A public, PKCE-only client (RFC 8252 native-app pattern, no client
secret) — `application_oauth_clients.client_secret_hash` (added in migration 0006 for
client_credentials) becomes nullable, and the table gains `redirect_uris`, shared by both methods'
registration but only populated for this one.

`authorization_codes` is single-use and short-lived (~2 minutes); `refresh_tokens` is opaque,
DB-backed, and reusable (not rotated on use), issued only when the authorization request's scope
included `offline_access`. Neither embeds any permission — every request re-resolves the
consenting identity's current profile via PermissionService, same as every other path.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-20

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("application_oauth_clients", "client_secret_hash", nullable=True)
    op.add_column(
        "application_oauth_clients", sa.Column("redirect_uris", JSONB, nullable=False, server_default="[]")
    )

    op.create_table(
        "authorization_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code_hash", sa.String, nullable=False, unique=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identity_id", UUID(as_uuid=True), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("redirect_uri", sa.String, nullable=False),
        sa.Column("code_challenge", sa.String, nullable=False),
        sa.Column("code_challenge_method", sa.String, nullable=False, server_default="S256"),
        sa.Column("scope", sa.String, nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String, nullable=False, unique=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identity_id", UUID(as_uuid=True), sa.ForeignKey("identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    for table in ("authorization_codes", "refresh_tokens"):
        op.execute(f"alter table {table} enable row level security")
        op.execute(
            f"""
            create policy tenant_isolation on {table} using (
              exists (select 1 from applications a where a.id = application_id and a.org_id = current_setting('app.org_id')::uuid)
            )
            """
        )


def downgrade():
    op.execute("drop policy tenant_isolation on refresh_tokens")
    op.execute("drop policy tenant_isolation on authorization_codes")
    op.drop_table("refresh_tokens")
    op.drop_table("authorization_codes")
    op.drop_column("application_oauth_clients", "redirect_uris")
    op.alter_column("application_oauth_clients", "client_secret_hash", nullable=False)
