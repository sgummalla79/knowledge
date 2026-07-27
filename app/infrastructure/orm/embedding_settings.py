import uuid

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.infrastructure.orm.base import Base


class EmbeddingSettings(Base):
    __tablename__ = "embedding_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    chunk_size = Column(Integer, nullable=False, default=DEFAULT_CHUNK_SIZE)
    chunk_overlap = Column(Integer, nullable=False, default=DEFAULT_CHUNK_OVERLAP)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
