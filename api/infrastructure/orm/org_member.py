import uuid

from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from api.infrastructure.orm.base import Base

org_member_role = ENUM("admin", "contributor", "viewer", name="user_role", create_type=False)


class OrgMember(Base):
    __tablename__ = "org_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    identity_id = Column(UUID(as_uuid=True), ForeignKey("identities.id", ondelete="CASCADE"), nullable=False)
    role = Column(org_member_role, nullable=False, default="viewer")
    invited_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
