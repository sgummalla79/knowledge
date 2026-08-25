import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from api.infrastructure.orm.base import Base

ingestion_type = ENUM("upload", "crawl", "resync", "reindex", name="ingestion_type", create_type=False)
ingestion_status = ENUM("queued", "processing", "indexed", "failed", name="ingestion_status", create_type=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    type = Column(ingestion_type, nullable=False)
    status = Column(ingestion_status, nullable=False, default="queued")
    error_message = Column(String, nullable=True)
    items_processed = Column(Integer, nullable=False, default=0)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # --- Release 1 of the standalone-worker migration (see migration 0018) ---
    # Request-time inputs a standalone worker process needs, durably -- today these only exist as
    # arguments passed straight into threading.Thread(...) and are lost the instant that thread's
    # stack unwinds.
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    # Upload-only. Path (relative to UPLOADS_DIR) to the originally-uploaded whole file on disk --
    # see api/infrastructure/storage/upload_storage.py and docs/UPLOAD_STORAGE_REDESIGN.md. A
    # plain string, unlike the old bytea `payload` column, so no deferred-loading trick is needed.
    payload_path = Column(String, nullable=True)
    payload_filename = Column(String, nullable=True)
    # Crawl-only.
    crawl_url = Column(String, nullable=True)
    crawl_max_pages = Column(Integer, nullable=True)
    crawl_scope_prefix = Column(String, nullable=True)

    # Live-progress fields -- durable equivalents of JobStore/CrawlJobStore's in-memory dict.
    cancel_requested = Column(Boolean, nullable=False, default=False)
    parts_total = Column(Integer, nullable=True)
    parts_completed = Column(Integer, nullable=False, default=0)
    parts_failed = Column(Integer, nullable=False, default=0)
    document_ids = Column(JSONB, nullable=False, default=list)
    pages = Column(JSONB, nullable=False, default=dict)

    # Claim bookkeeping -- observability only, not correctness (FOR UPDATE SKIP LOCKED is what
    # makes claiming itself correct). claimed_by is a free-text worker instance id, not a FK.
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_by = Column(String, nullable=True)
