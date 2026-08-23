from sqlalchemy import Boolean, Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class MCPSettings(Base):
    __tablename__ = "mcp_settings"

    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    search_read_enabled = Column(Boolean, nullable=False, default=False)
    object_read_enabled = Column(Boolean, nullable=False, default=False)
    object_write_enabled = Column(Boolean, nullable=False, default=False)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    last_modified_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
