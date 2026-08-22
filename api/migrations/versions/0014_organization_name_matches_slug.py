"""backfill organizations.name to match slug

An org's name and slug have been the same value by construction since item 17/18's work
(self-serve signup validates the user-typed org name as already slug-shaped and stores it verbatim
as both columns — see org_name_validation.py, OrgMembershipService.create_org_with_owner) — but
that was never true for the pre-existing bootstrap default org, whose name
("Default Organization", from the now-removed DEFAULT_ORGANIZATION_NAME constant) neither matches
its slug ("default") nor is slug-shaped itself (spaces, uppercase). Any org created via the old,
now-removed "create another org" flow (free-text name, auto-derived slug) has a similar mismatch,
just less visibly malformed, since slugify() always produced a valid slug-shaped value even when
the free-text name didn't match it.

Backfills every mismatched row to `name = slug` — slug is always already valid-shaped (unique,
checked at creation), so this is a safe, blanket fix rather than needing to re-validate anything.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-21

"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE organizations SET name = slug WHERE name != slug")


def downgrade():
    # The pre-migration `name` values aren't recoverable (never stored anywhere else) — nothing to
    # reverse to.
    pass
