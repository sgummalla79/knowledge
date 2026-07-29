from sqlalchemy import Boolean, Column, DateTime, String, func

from app.infrastructure.orm.base import Base


class EmbeddingProviderSetting(Base):
    __tablename__ = "embedding_provider_settings"

    # The provider's registry key (e.g. "voyage") is a stable identifier, not a value that ever
    # gets edited in place — a natural primary key, no separate surrogate UUID needed.
    provider = Column(String, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
