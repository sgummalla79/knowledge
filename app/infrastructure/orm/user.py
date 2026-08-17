import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from app.infrastructure.orm.base import Base

user_role = ENUM("admin", "contributor", "viewer", name="user_role", create_type=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(user_role, nullable=False, default="viewer")
    password_hash = Column(String, nullable=False)
    must_change_password = Column(Boolean, nullable=False, default=True)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_active_at = Column(DateTime(timezone=True), nullable=True)
