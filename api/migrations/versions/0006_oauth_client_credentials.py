"""connected applications: oauth_client_credentials auth method (phase B of the connected-
applications feature)

Adds `applications.execute_as_identity_id` (set only for oauth_client_credentials — the real,
already-existing org member a token from this application resolves to; PermissionService resolves
its permissions the same way it does for a human session, see api/application/permission_service.py)
and `application_oauth_clients` (the client_secret credential for that method — application_id
itself is the wire-format client_id, so there's no separate client_id column).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-20

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "applications", sa.Column("execute_as_identity_id", UUID(as_uuid=True), sa.ForeignKey("identities.id"), nullable=True)
    )

    op.create_table(
        "application_oauth_clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("client_secret_hash", sa.String, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("alter table application_oauth_clients enable row level security")
    op.execute(
        """
        create policy tenant_isolation on application_oauth_clients using (
          exists (select 1 from applications a where a.id = application_id and a.org_id = current_setting('app.org_id')::uuid)
        )
        """
    )


def downgrade():
    op.execute("drop policy tenant_isolation on application_oauth_clients")
    op.drop_table("application_oauth_clients")
    op.drop_column("applications", "execute_as_identity_id")
