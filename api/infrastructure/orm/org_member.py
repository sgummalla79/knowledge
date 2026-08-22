import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class OrgMember(Base):
    __tablename__ = "org_members"
    # identity_id is unique, not just (org_id, identity_id) — an identity belongs to exactly one
    # org for its whole life (see domain/entities.py's Identity docstring), so there's no longer a
    # many-to-many to guard against, only ever-adding-a-second-org for the same identity.
    __table_args__ = (UniqueConstraint("identity_id", name="uq_org_members_identity_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    identity_id = Column(UUID(as_uuid=True), ForeignKey("identities.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
