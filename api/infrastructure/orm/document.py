import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from api.infrastructure.orm.base import Base

document_type = ENUM(
    "article", "document", name="document_type", create_type=False
)
document_status = ENUM("processing", "indexed", "failed", "archived", name="document_status", create_type=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=False)
    # The browsable/editable display name — replaces the old `source_filename` (same renameable
    # field, see DocumentRepository.rename).
    title = Column(String, nullable=False)
    # Content classification (article/document) — distinct from `file_type` below, which is the
    # technical upload format (pdf/md/txt/html) driving parser selection
    # (api/infrastructure/parsing/registry.py). Assigned at ingestion time by a simple rule
    # (IngestionService: a crawl is always "article", an upload is "document") and editable after
    # the fact via PATCH /documents/<id>/metadata. No "media" (image/video/audio) type for now —
    # this app has no model that can meaningfully embed or retrieve that content yet; add it back
    # once one exists, rather than keeping a label with nothing real behind it.
    type = Column(document_type, nullable=False)
    # Pointer to blob storage — nullable and unpopulated for now, no blob storage exists yet.
    # Uploads live in raw_file_path below instead (see migration 0001's docstring and migration
    # 0019, which moved that column from a bytea value to a path on disk).
    content_uri = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(document_status, nullable=False, default="processing")
    # Extensions beyond the target spec: parser selection, dedup, retry-on-failure, oversized-PDF
    # splitting, chunk-count reporting — real features the spec's author wasn't accounting for.
    file_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    # Path (relative to UPLOADS_DIR) to the exact bytes this document (or, for a split PDF, one
    # part) was created from — see api/infrastructure/storage/upload_storage.py and
    # docs/UPLOAD_STORAGE_REDESIGN.md. Kept only until this document reaches "indexed" (a failed
    # ingestion can be retried without the client re-sending the file), same lifetime the old
    # bytea `raw_file_bytes` column had. A plain string, so no deferred-loading trick is needed.
    raw_file_path = Column(String, nullable=True)
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
    created_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
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
