"""Case-insensitive tag name uniqueness

Tag name uniqueness (tags.org_id, tags.name) was a plain, case-sensitive btree constraint —
"Billing" and "billing" could coexist as two distinct tags. The only thing preventing that in
practice was a client-side pre-check in webui's TagPillInput, which every other caller (a direct
API client, Postman, the MCP object-write tier's create_tag tool) bypassed entirely. Moved
server-side: TagService.create_tag now does a case-insensitive get-or-create
(TagRepository.find_by_name_ci), and this migration makes the DB itself enforce it so a race
between two concurrent creates can't slip a case-variant duplicate past the lookup.

Before adding the case-insensitive unique index, any pre-existing case-variant duplicates (e.g. a
prior "Billing" and "billing" in the same org) would make the index creation fail — so this first
merges each such group onto one canonical row (oldest by created_at, tie-broken by id), repoints
document_tags rows from the duplicates onto the canonical tag (skipping a repoint that would
collide with a (document_id, tag_id) pair the canonical tag already has, then dropping the
now-redundant duplicate row), and deletes the duplicate tags. Expected to be a no-op on most
databases — nothing in the app has been able to create such a pair before now other than a narrow
race, which the old case-sensitive constraint already closed for exact-name duplicates — this is
defensive, not a known-needed cleanup.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-22

"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

# Every duplicate-merge statement below needs the same "which tag is canonical for this
# (org_id, lower(name)) group" answer, so it's factored out and reused rather than repeating the
# window-function logic three times with room for the copies to drift.
_CANONICAL_MAP_CTE = """
    WITH canonical_map AS (
        SELECT id,
               first_value(id) OVER (
                   PARTITION BY org_id, lower(name)
                   ORDER BY created_at ASC, id ASC
                   ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
               ) AS canonical_id
        FROM tags
    )
"""


def upgrade():
    # Repoint document_tags rows from a duplicate tag onto its canonical tag — unless the
    # document is already tagged with the canonical tag too, in which case repointing would
    # violate document_tags' (document_id, tag_id) primary key; that row is just dropped instead
    # (next statement) since the tagging relationship it represents already exists.
    op.execute(
        _CANONICAL_MAP_CTE
        + """
        UPDATE document_tags dt
        SET tag_id = m.canonical_id
        FROM canonical_map m
        WHERE dt.tag_id = m.id
          AND m.id != m.canonical_id
          AND NOT EXISTS (
              SELECT 1 FROM document_tags existing
              WHERE existing.document_id = dt.document_id AND existing.tag_id = m.canonical_id
          )
        """
    )
    op.execute(
        _CANONICAL_MAP_CTE
        + """
        DELETE FROM document_tags dt
        USING canonical_map m
        WHERE dt.tag_id = m.id AND m.id != m.canonical_id
        """
    )
    op.execute(
        _CANONICAL_MAP_CTE
        + """
        DELETE FROM tags t
        USING canonical_map m
        WHERE t.id = m.id AND m.id != m.canonical_id
        """
    )

    op.drop_constraint("uq_tags_org_id_name", "tags", type_="unique")
    op.execute("CREATE UNIQUE INDEX uq_tags_org_id_name_ci ON tags (org_id, lower(name))")


def downgrade():
    op.execute("DROP INDEX uq_tags_org_id_name_ci")
    op.create_unique_constraint("uq_tags_org_id_name", "tags", ["org_id", "name"])
    # The case-variant duplicates merged in upgrade() aren't recoverable (the rows were deleted,
    # not archived) — nothing to reverse there.
