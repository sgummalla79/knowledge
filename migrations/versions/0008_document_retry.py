"""documents: raw_file_bytes + error_message, to support retrying a failed ingestion

raw_file_bytes stores the original uploaded file so a failed document can be retried without the
client re-sending it — cleared back to NULL the moment a document reaches "completed" (see
DocumentRepository.update_status), so sustained storage cost is bounded by currently-processing-
or-failed documents only, not the full historical upload volume. error_message persists the
failure reason (previously only visible in the ephemeral, in-memory JobStore) so a client can
decide whether retrying is even worth it before doing so.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("raw_file_bytes", sa.LargeBinary, nullable=True))
    op.add_column("documents", sa.Column("error_message", sa.String, nullable=True))


def downgrade():
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "raw_file_bytes")
