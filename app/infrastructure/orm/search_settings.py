import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class SearchSettings(Base):
    __tablename__ = "search_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dense_k = Column(Integer, nullable=False)
    sparse_k = Column(Integer, nullable=False)
    rrf_k = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # Additive multi-tenant-migration column (migration 0024) — nullable and unused by
    # SearchSettingsRepository yet. See that migration's docstring.
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
