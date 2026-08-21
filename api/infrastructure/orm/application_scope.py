from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class ApplicationScope(Base):
    __tablename__ = "application_scopes"

    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    scope = Column(String, primary_key=True)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
