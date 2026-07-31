import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

from app.infrastructure.orm.base import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    library_id = Column(UUID(as_uuid=True), ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    # Generated column (see migration 0003) — Postgres keeps this in sync with `content` on every
    # write, so it's mapped read-only here purely so sparse_search() can reference it in queries.
    content_tsv = Column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True), nullable=False)
    # Deliberately dimensionless (no Vector(N)): a fixed dim here is a Python-side constant baked
    # in at process-import time, but ChunkRepository.resize_embedding_column() changes the real
    # column's width with raw SQL at runtime — a value this class could never see or track without
    # a process restart re-reading a stale constant. A fixed dim would make pgvector's client-side
    # bind_processor reject perfectly valid vectors any time the *actual* column width has moved
    # away from whatever constant was compiled in (exactly what happened here: a routine app
    # restart silently reverted enforcement to the original 768, rejecting real 1024-dim Voyage
    # vectors even though the live column was correctly already vector(1024)). Leaving it
    # dimensionless defers all enforcement to Postgres's own column constraint, which is always
    # accurate regardless of process lifetime — app/application/ingestion_service.py's explicit
    # settings.dimensions check is the friendly-error safety net ahead of that.
    embedding = Column(Vector(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self, distance=None):
        result = {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "chunk_index": self.chunk_index,
            "content": self.content,
        }
        if distance is not None:
            result["distance"] = float(distance)
        return result
