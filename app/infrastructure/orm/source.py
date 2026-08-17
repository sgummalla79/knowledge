import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from app.infrastructure.orm.base import Base

source_type = ENUM("upload", "url", "connector", name="source_type", create_type=False)
source_status = ENUM("active", "paused", "error", name="source_status", create_type=False)


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    type = Column(source_type, nullable=False)
    name = Column(String, nullable=False)
    config = Column(JSONB, nullable=False, default=dict)
    api_key_hash = Column(String, nullable=True)
    status = Column(source_status, nullable=False, default="active")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
