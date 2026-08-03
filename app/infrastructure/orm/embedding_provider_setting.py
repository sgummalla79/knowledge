import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class EmbeddingProviderSetting(Base):
    __tablename__ = "embedding_provider_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The registry key (e.g. "voyage") is the business identifier every lookup/route addresses
    # this row by — unique, not the primary key, matching every other table's uuid-id + unique
    # natural-key pattern (libraries.name, users.username, applications.name).
    provider = Column(String, nullable=False, unique=True)
    # "This is the one provider actually used for embedding" — at most one row may have this set
    # (enforced by ix_embedding_provider_settings_single_enabled, migration 0015), since the app
    # embeds with a single global model, not a per-library choice.
    enabled = Column(Boolean, nullable=False, default=False)
    model = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    dimensions = Column(Integer, nullable=True)
    chunk_size = Column(Integer, nullable=True)
    chunk_overlap = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
