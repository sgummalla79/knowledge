"""oauth authorization_code grant: redirect_uris on applications, authorization_codes table

Adds what's needed for a spec-faithful OAuth2 authorization_code + PKCE flow (RFC 6749 + RFC 7636)
alongside the existing client_credentials/refresh_token grants — registered clients now carry an
allowlist of redirect URIs, and issued authorization codes are short-lived, single-use, and stored
hash-only (mirrors refresh_tokens' token_hash convention).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("redirect_uris", sa.String, nullable=True))

    op.create_table(
        "authorization_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String, nullable=False, unique=True),
        sa.Column("redirect_uri", sa.String, nullable=False),
        sa.Column("code_challenge", sa.String, nullable=False),
        sa.Column("code_challenge_method", sa.String, nullable=False),
        sa.Column("scope", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_authorization_codes_application_id", "authorization_codes", ["application_id"])


def downgrade():
    op.drop_table("authorization_codes")
    op.drop_column("applications", "redirect_uris")
