import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import deferred

from app.infrastructure.orm.base import Base

document_type = ENUM(
    "article", "dataset", "guide", "report", "faq", "media", name="document_type", create_type=False
)
document_status = ENUM("processing", "indexed", "failed", "archived", name="document_status", create_type=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # The browsable/editable display name — replaces the old `source_filename` (same renameable
    # field, see DocumentRepository.rename).
    title = Column(String, nullable=False)
    # Classification (article/dataset/guide/report/faq/media) per the target spec — distinct from
    # `file_type` below, which is the technical upload format (pdf/md/txt/html) driving parser
    # selection (app/infrastructure/parsing/registry.py). Nothing sets this classification yet.
    type = Column(document_type, nullable=False)
    # Pointer to blob storage — nullable and unpopulated for now, no blob storage exists yet.
    # Uploads live in raw_file_bytes below instead (see migration 0001's docstring).
    content_uri = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(document_status, nullable=False, default="processing")
    # Extensions beyond the target spec: parser selection, dedup, retry-on-failure, oversized-PDF
    # splitting, chunk-count reporting — real features the spec's author wasn't accounting for.
    file_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    # Deferred: only loaded when explicitly accessed (DocumentRepository.get_raw_bytes), not on
    # every plain get()/list_for_org() query — those don't need this column and it can be up to
    # MAX_UPLOAD_MB per row, so loading it unconditionally on every list call would be wasteful.
    raw_file_bytes = deferred(Column(LargeBinary, nullable=True))
    error_message = Column(String, nullable=True)
    # Set once at upload time (IngestionService.ingest) — the byte count is already in hand then,
    # no extra work needed.
    size_bytes = Column(Integer, nullable=True)
    # Set once ingestion actually completes — stays NULL for processing/failed documents, so API
    # consumers can tell "not available yet" apart from "genuinely zero chunks".
    chunk_count = Column(Integer, nullable=True)
    # Set together, only for a document created as one part of an auto-split oversized PDF
    # (PdfSplitIngestionService) — all three stay NULL for an ordinary, unsplit document.
    split_group_id = Column(UUID(as_uuid=True), nullable=True)
    split_part = Column(Integer, nullable=True)
    split_total = Column(Integer, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "title": self.title,
            "file_type": self.file_type,
            "type": self.type,
            "status": self.status,
            "split_group_id": str(self.split_group_id) if self.split_group_id else None,
            "split_part": self.split_part,
            "split_total": self.split_total,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
