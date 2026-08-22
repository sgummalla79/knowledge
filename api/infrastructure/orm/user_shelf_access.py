from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class UserShelfAccess(Base):
    __tablename__ = "user_shelf_access"

    user_id = Column(UUID(as_uuid=True), ForeignKey("identities.id", ondelete="CASCADE"), primary_key=True)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
