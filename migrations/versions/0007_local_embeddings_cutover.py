"""local embeddings: cut chunks.embedding over to 768-dim (drop old, promote embedding_new)

Step 2 of 2 (see migration 0006). DO NOT ship/deploy this migration until
`python -m app.cli reembed-chunks --provider ollama --model nomic-embed-text` has been run to
completion against the target database and `SELECT count(*) FROM chunks WHERE embedding_new IS
NULL` returns 0 — this migration's guard re-verifies that and aborts loudly if it doesn't hold,
but the re-embed itself must happen out-of-band, manually, during a maintenance window (it's a
long-running, network-bound operation; it cannot run inside a migration, and `alembic upgrade
head` runs automatically on every container start, so there is no way to pause between migrations
in a single deploy).

Full prod rollout runbook:
  1. Back up the database (pg_dump or volume snapshot) — downgrade() below is irreversible.
  2. Deploy an image containing migration 0006 + the new Ollama provider code, but NOT this
     migration yet.
  3. Run `python -m app.cli reembed-chunks --provider ollama --model nomic-embed-text` against
     that deployment.
  4. Verify `SELECT count(*) FROM chunks WHERE embedding_new IS NULL` returns 0.
  5. Deploy this migration.

On a fresh database, chunks.embedding is already created at the current EMBEDDING_DIM (768) by
migration 0001, so this migration is a harmless no-op on zero rows (guard trivially passes; the
add/drop/rename churn is cosmetic).

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-27

"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        DECLARE missing int;
        BEGIN
            SELECT count(*) INTO missing FROM chunks WHERE embedding_new IS NULL;
            IF missing > 0 THEN
                RAISE EXCEPTION
                    'reembed incomplete: % chunks missing embedding_new — run '
                    '"python -m app.cli reembed-chunks" first', missing;
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_column("chunks", "embedding")
    op.alter_column("chunks", "embedding_new", new_column_name="embedding")
    op.alter_column("chunks", "embedding", nullable=False)
    op.execute("CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
    # Any settings row still pointing at the now-incompatible 1024-dim Voyage provider is flipped
    # to the new default so ingestion/retrieval don't try to write/read a dimension mismatch.
    # Deterministic, no network call (unlike the re-embed step) — safe to run inline here.
    op.execute(
        """
        UPDATE embedding_settings
        SET provider = 'ollama', model = 'nomic-embed-text', api_key = NULL
        WHERE provider = 'voyage'
        """
    )


def downgrade():
    raise RuntimeError(
        "irreversible: the old 1024-dim embedding column was dropped in upgrade() — restore from "
        "the pre-migration backup instead of downgrading."
    )
