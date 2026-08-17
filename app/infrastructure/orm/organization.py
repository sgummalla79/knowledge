import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from app.infrastructure.orm.base import Base

org_plan = ENUM("free", "team", "enterprise", name="org_plan", create_type=False)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    plan = Column(org_plan, nullable=False, default="free")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
