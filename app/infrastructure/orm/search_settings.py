import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class SearchSettings(Base):
    __tablename__ = "search_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rerank_enabled = Column(Boolean, nullable=False)
    rerank_provider = Column(String, nullable=False)
    rerank_model = Column(String, nullable=False)
    dense_k = Column(Integer, nullable=False)
    sparse_k = Column(Integer, nullable=False)
    rerank_candidates = Column(Integer, nullable=False)
    rrf_k = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
