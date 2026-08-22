"""identities.username + cap an identity to exactly one org

Reverses a design decision migration 0001's module docstring made explicit: "one identity can
belong to many orgs and switch between them, each with its own role." In practice that capability
was never reachable from the UI (no org switcher was ever built, no "create another org" button
existed) and the product direction settled on something simpler: a login identity is scoped to
exactly one org for its whole life, decided the moment it's created (self-serve signup, or —
later — an invite). `org_members.identity_id` becomes unique to enforce that; the old
`uq_org_members_org_id_identity_id` composite constraint (and its now-redundant plain index on
identity_id) are dropped in favor of it.

Splits "the string identifying who's logging in" from "a real, deliverable email address," which
used to be the same column (`identities.email`, unique) and are now two:

- `username`: new, required, unique — must be email-*shaped* (validated in
  api/application/username_validation.py) but not verified as deliverable. This is what
  PasswordIdentityVerifier authenticates against now, not `email`.
- `email`: kept, but no longer unique or required — real contact info only. The same real email
  can now recur across (or even within) different orgs' identities, since it carries no identity
  weight of its own.

Existing rows are backfilled with `username = email` (every identity created so far already used
an email-shaped value there, including the bootstrapped admin, whose DEFAULT_ADMIN_USERNAME
becomes "admin@local" going forward — this migration only backfills what's already in the
database, it doesn't rewrite old values to match the new default).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-21

"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("identities", sa.Column("username", sa.String, nullable=True))
    op.execute("UPDATE identities SET username = email")
    op.alter_column("identities", "username", nullable=False)
    op.create_unique_constraint("uq_identities_username", "identities", ["username"])

    op.drop_constraint("uq_identities_email", "identities", type_="unique")
    op.alter_column("identities", "email", nullable=True)

    op.drop_index("ix_org_members_identity_id", table_name="org_members")
    op.drop_constraint("uq_org_members_org_id_identity_id", "org_members", type_="unique")
    op.create_unique_constraint("uq_org_members_identity_id", "org_members", ["identity_id"])


def downgrade():
    op.drop_constraint("uq_org_members_identity_id", "org_members", type_="unique")
    op.create_unique_constraint("uq_org_members_org_id_identity_id", "org_members", ["org_id", "identity_id"])
    op.create_index("ix_org_members_identity_id", "org_members", ["identity_id"])

    op.execute("UPDATE identities SET email = username WHERE email IS NULL")
    op.alter_column("identities", "email", nullable=False)
    op.create_unique_constraint("uq_identities_email", "identities", ["email"])

    op.drop_constraint("uq_identities_username", "identities", type_="unique")
    op.drop_column("identities", "username")
