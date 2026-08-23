import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from api.infrastructure.orm.base import Base

embed_provider = ENUM("voyage", "openai_compatible", name="embed_provider", create_type=False)
embed_model_status = ENUM("active", "retired", "disabled", name="embed_model_status", create_type=False)


class EmbeddingModel(Base):
    __tablename__ = "embedding_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    provider = Column(embed_provider, nullable=False)
    name = Column(String, nullable=False)
    model_identifier = Column(String, nullable=False)
    dimensions = Column(Integer, nullable=False)
    endpoint_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    # At most one status='active' row per org (embedding_models_one_active_per_org, migration
    # 0026) — the one used for new ingestion; is_default can only be true when status='active'
    # (embedding_models_default_is_active check constraint). This app doesn't yet have a caller
    # that sets is_default/status independently — see EmbeddingSettingsRepository/
    # EmbeddingProviderSettingsRepository, which keep them in lockstep for now, same "exactly one
    # active provider" semantics as the table this one replaced. A row with existing chunks can
    # never return to 'disabled' or be deleted (guard_embedding_model_change trigger, migration
    # 0026) — its only remaining transition is 'retired'.
    is_default = Column(Boolean, nullable=False, default=False)
    status = Column(embed_model_status, nullable=False, default="disabled")
    chunk_size = Column(Integer, nullable=False)
    chunk_overlap = Column(Integer, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
