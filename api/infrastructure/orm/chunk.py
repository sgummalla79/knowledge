import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID

from api.infrastructure.orm.base import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    ordinal = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    # Generated column (see migration 0001) — Postgres keeps this in sync with `content` on every
    # write, so it's mapped read-only here purely so sparse_search() can reference it in queries.
    # Not part of the target spec (see migration 0001's docstring) — it's the sparse half of this
    # app's hybrid (dense+sparse RRF) search.
    content_tsv = Column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True), nullable=False)
    token_count = Column(Integer, nullable=False)
    # Deliberately dimensionless (no Vector(N)): a fixed dim here is a Python-side constant baked
    # in at process-import time, but ChunkRepository.resize_embedding_column() changes the real
    # column's width with raw SQL at runtime. Also a genuine deviation from the target spec's fixed
    # vector(1536) — per-org "bring your own embedding model" means different orgs can have
    # different dimensions, which a single fixed-width column can't represent (see migration
    # 0001's docstring).
    embedding = Column(Vector(), nullable=False)
    embedding_model_id = Column(UUID(as_uuid=True), ForeignKey("embedding_models.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self, distance=None):
        result = {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "ordinal": self.ordinal,
            "content": self.content,
        }
        if distance is not None:
            result["distance"] = float(distance)
        return result
