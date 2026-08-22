"""applications.api_access — a channel flag symmetric to mcp_access (migration 0008), gating
whether a connected application may call the plain REST API at all.

Before this, REST API reachability was implicit: for api_key it fell out of whatever
application_scopes were granted, and for the two OAuth methods it fell out of whatever the
connected identity's profile allowed — there was no single on/off switch independent of those.
Defaults to true (unlike mcp_access's default-false) since REST API access is this app's original,
primary purpose — every application created before this migration already has full use of
whatever its scopes/profile grant, and this column must not silently revoke that.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("api_access", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("applications", "api_access")
