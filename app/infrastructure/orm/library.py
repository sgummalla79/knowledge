import uuid

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
)
from app.infrastructure.orm.base import Base


class Library(Base):
    __tablename__ = "libraries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    embedding_provider = Column(String, nullable=False, default=DEFAULT_EMBEDDING_PROVIDER)
    embedding_model = Column(String, nullable=False, default=DEFAULT_EMBEDDING_MODEL)
    chunk_size = Column(Integer, nullable=False, default=DEFAULT_CHUNK_SIZE)
    chunk_overlap = Column(Integer, nullable=False, default=DEFAULT_CHUNK_OVERLAP)
    document_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    last_ingested_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "last_ingested_at": self.last_ingested_at.isoformat() if self.last_ingested_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
