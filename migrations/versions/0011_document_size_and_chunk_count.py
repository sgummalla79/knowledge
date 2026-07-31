"""documents: size_bytes + chunk_count, for the document list/detail API response

size_bytes is set once at upload time (the byte count is already in hand — no extra work at
ingest time). chunk_count is set once ingestion actually completes (see
IngestionService._process), staying NULL for pending/processing/failed documents so a client can
tell "not available yet" apart from "genuinely zero chunks" instead of just seeing 0.

Backfilled for existing rows where the value is still derivable: chunk_count from the real chunk
rows for anything already completed; size_bytes from the still-present raw_file_bytes for
anything not yet completed (raw_file_bytes is cleared once a document reaches "completed" — see
DocumentRepository.update_status — so a completed document's original upload size can no longer
be recovered).

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-29

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("size_bytes", sa.Integer, nullable=True))
    op.add_column("documents", sa.Column("chunk_count", sa.Integer, nullable=True))
    op.execute(
        """
        UPDATE documents
        SET chunk_count = (SELECT COUNT(*) FROM chunks WHERE chunks.document_id = documents.id)
        WHERE status = 'completed'
        """
    )
    op.execute("UPDATE documents SET size_bytes = length(raw_file_bytes) WHERE raw_file_bytes IS NOT NULL")


def downgrade():
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "size_bytes")
