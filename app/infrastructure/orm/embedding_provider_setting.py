import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class EmbeddingProviderSetting(Base):
    __tablename__ = "embedding_provider_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The registry key (e.g. "voyage") is the business identifier every lookup/route addresses
    # this row by — unique, not the primary key, matching every other table's uuid-id + unique
    # natural-key pattern (libraries.name, users.username, applications.name).
    provider = Column(String, nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
