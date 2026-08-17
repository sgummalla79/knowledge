import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from app.infrastructure.orm.base import Base

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
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
