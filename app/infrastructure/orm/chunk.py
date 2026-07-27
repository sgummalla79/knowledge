import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

from app.constants import EMBEDDING_DIM
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
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
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
