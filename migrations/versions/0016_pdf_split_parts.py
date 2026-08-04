"""documents: split_group_id + split_part + split_total, for auto-split oversized PDFs

An oversized PDF (over MAX_UPLOAD_MB) is now split into multiple parts on ingest
(PdfSplitter/PdfSplitIngestionService) instead of being rejected outright. Each part is an
ordinary Document row created via the existing IngestionService.ingest() pipeline unchanged; these
three columns are purely traceability/grouping metadata so a client can tell which documents came
from the same original upload. All three stay NULL for a document that was never split — the
correct default, needing no backfill for existing rows.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("split_group_id", UUID(as_uuid=True), nullable=True))
    op.add_column("documents", sa.Column("split_part", sa.Integer, nullable=True))
    op.add_column("documents", sa.Column("split_total", sa.Integer, nullable=True))
    op.create_index(
        "ix_documents_split_group_id",
        "documents",
        ["split_group_id"],
        postgresql_where=sa.text("split_group_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("ix_documents_split_group_id", table_name="documents")
    op.drop_column("documents", "split_total")
    op.drop_column("documents", "split_part")
    op.drop_column("documents", "split_group_id")
