"""Replace bytea upload storage with on-disk paths (see docs/UPLOAD_STORAGE_REDESIGN.md)

Raw uploaded/ingested file bytes moved off Postgres (ingestion_jobs.payload,
documents.raw_file_bytes) onto a local disk volume (api/infrastructure/storage/upload_storage.py)
-- the root cause of a chain of OOM/DB-crash incidents documented in that redesign doc, worst of
which OOM-killed the Postgres container itself on a large upload's INSERT.

ingestion_jobs.payload (bytea) -> payload_path (text): the path to the originally-uploaded whole
file, written by the upload route via a streaming save (never materialized as one Python bytes
object), read once by the worker.

documents.raw_file_bytes (bytea) -> raw_file_path (text): the path to the exact bytes a given
document (or, for a split PDF, one part) was created from -- kept until that document reaches
"indexed", same "kept for retry until indexed" lifetime the bytea column already had.

No backfill: both columns are already-cleared/short-lived in every existing row (payload is
nulled once the worker reads it; raw_file_bytes is nulled once a document reaches "indexed"), so
there's nothing meaningful to carry forward -- see the redesign doc's own note on this.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ingestion_jobs", sa.Column("payload_path", sa.String, nullable=True))
    op.drop_column("ingestion_jobs", "payload")

    op.add_column("documents", sa.Column("raw_file_path", sa.String, nullable=True))
    op.drop_column("documents", "raw_file_bytes")


def downgrade():
    op.add_column("documents", sa.Column("raw_file_bytes", sa.LargeBinary, nullable=True))
    op.drop_column("documents", "raw_file_path")

    op.add_column("ingestion_jobs", sa.Column("payload", sa.LargeBinary, nullable=True))
    op.drop_column("ingestion_jobs", "payload_path")
