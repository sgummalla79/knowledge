"""Additive queue columns on ingestion_jobs (Release 1 of the standalone-worker migration)

ingestion_jobs today is a best-effort *secondary* record (api/application/document_service.py's
_persist_job_status) alongside two in-memory, process-local stores that are the actual source of
truth for live job status/progress -- JobStore (api/application/job_store.py) and CrawlJobStore
(api/application/crawl_job_store.py), which is exactly why this app is pinned to one gunicorn
worker / one k8s replica (see api/deploy/entrypoint.sh's and api/deploy/k3s/02-api.yaml's own
comments). This migration adds the columns a standalone worker process needs to eventually become
the *primary* source of truth (a later, separate release): durable copies of request-time inputs
that today only live in a Python function argument handed straight to threading.Thread (uploaded
file bytes/filename, category_id, crawl url/max_pages/scope_prefix), plus the same live-progress
fields JobStore/CrawlJobStore already track in memory (cancel_requested, split-PDF
parts_total/parts_completed/parts_failed/document_ids, per-page crawl status).

Purely additive -- every new column is nullable or defaulted, no existing column/constraint
changes, no data migration. Nothing in the live request path writes or reads these columns yet;
this just makes the schema ready for the worker introduced alongside this migration.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-24

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    # Request-time inputs a worker needs to actually run the job -- today these only exist as
    # arguments passed straight into threading.Thread(target=..., args=(...)) and are lost the
    # instant that thread's stack unwinds.
    op.add_column("ingestion_jobs", sa.Column("category_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "ingestion_jobs_category_id_fkey",
        "ingestion_jobs",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Upload-only. bytea, same type/nullable/deferred-load convention as documents.raw_file_bytes
    # (migration 0001) -- cleared back to NULL once the worker has read it (a later release), so
    # this table never holds an upload's bytes for longer than it takes to process the job.
    op.add_column("ingestion_jobs", sa.Column("payload", sa.LargeBinary, nullable=True))
    op.add_column("ingestion_jobs", sa.Column("payload_filename", sa.String, nullable=True))
    # Crawl-only.
    op.add_column("ingestion_jobs", sa.Column("crawl_url", sa.String, nullable=True))
    op.add_column("ingestion_jobs", sa.Column("crawl_max_pages", sa.Integer, nullable=True))
    op.add_column("ingestion_jobs", sa.Column("crawl_scope_prefix", sa.String, nullable=True))

    # Live-progress fields -- durable equivalents of JobStore/CrawlJobStore's in-memory dict.
    op.add_column(
        "ingestion_jobs", sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default="false")
    )
    # Upload-only, split-PDF progress (PdfSplitIngestionService). parts_total stays NULL until the
    # first part result arrives (unknown before ingestion starts -- splitting requires parsing the
    # PDF's page count first), same meaning JobStore.parts_total already carries.
    op.add_column("ingestion_jobs", sa.Column("parts_total", sa.Integer, nullable=True))
    op.add_column(
        "ingestion_jobs", sa.Column("parts_completed", sa.Integer, nullable=False, server_default="0")
    )
    op.add_column("ingestion_jobs", sa.Column("parts_failed", sa.Integer, nullable=False, server_default="0"))
    op.add_column(
        "ingestion_jobs",
        sa.Column("document_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    # Crawl-only, per-page status -- {url: {"status": ..., "document_id": ..., "error": ...}},
    # same shape CrawlJobStore.pages already uses.
    op.add_column(
        "ingestion_jobs", sa.Column("pages", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    )

    # Claim bookkeeping -- observability only (FOR UPDATE SKIP LOCKED is what makes claiming
    # itself correct; these two columns exist so a stuck/crashed claim is visible and debuggable,
    # not to enforce anything). claimed_by is a free-text worker instance id (hostname:pid), not a
    # foreign key to anything.
    op.add_column("ingestion_jobs", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("claimed_by", sa.String, nullable=True))


def downgrade():
    op.drop_column("ingestion_jobs", "claimed_by")
    op.drop_column("ingestion_jobs", "claimed_at")
    op.drop_column("ingestion_jobs", "pages")
    op.drop_column("ingestion_jobs", "document_ids")
    op.drop_column("ingestion_jobs", "parts_failed")
    op.drop_column("ingestion_jobs", "parts_completed")
    op.drop_column("ingestion_jobs", "parts_total")
    op.drop_column("ingestion_jobs", "cancel_requested")
    op.drop_column("ingestion_jobs", "crawl_scope_prefix")
    op.drop_column("ingestion_jobs", "crawl_max_pages")
    op.drop_column("ingestion_jobs", "crawl_url")
    op.drop_column("ingestion_jobs", "payload_filename")
    op.drop_column("ingestion_jobs", "payload")
    op.drop_constraint("ingestion_jobs_category_id_fkey", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "category_id")
