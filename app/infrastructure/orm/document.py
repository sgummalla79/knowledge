import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import deferred

from app.infrastructure.orm.base import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_id = Column(UUID(as_uuid=True), ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    source_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    # Deferred: only loaded when explicitly accessed (DocumentRepository.get_raw_bytes), not on
    # every plain get()/list_for_library() query — those don't need this column and it can be up
    # to MAX_UPLOAD_MB per row, so loading it unconditionally on every list call would be wasteful.
    raw_file_bytes = deferred(Column(LargeBinary, nullable=True))
    error_message = Column(String, nullable=True)
    # Set once at upload time (IngestionService.ingest) — the byte count is already in hand then,
    # no extra work needed.
    size_bytes = Column(Integer, nullable=True)
    # Set once ingestion actually completes (IngestionService._process) — stays NULL for
    # pending/processing/failed documents, so API consumers can tell "not available yet" apart
    # from "genuinely zero chunks" instead of just seeing 0.
    chunk_count = Column(Integer, nullable=True)
    # Set together, only for a document created as one part of an auto-split oversized PDF
    # (PdfSplitIngestionService) — all three stay NULL for an ordinary, unsplit document. Purely
    # grouping/traceability metadata: each part is otherwise an entirely ordinary Document row,
    # ingested/retried through the same IngestionService.ingest()/retry() as any other document.
    split_group_id = Column(UUID(as_uuid=True), nullable=True)
    split_part = Column(Integer, nullable=True)
    split_total = Column(Integer, nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "library_id": str(self.library_id),
            "source_filename": self.source_filename,
            "file_type": self.file_type,
            "status": self.status,
            "split_group_id": str(self.split_group_id) if self.split_group_id else None,
            "split_part": self.split_part,
            "split_total": self.split_total,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
