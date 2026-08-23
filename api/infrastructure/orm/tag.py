import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Case-insensitive — "Billing" and "billing" collide (migration 0016). TagService.create_tag
    # looks up by the same case-insensitive rule before inserting, so this index is a concurrency
    # backstop (two simultaneous creates of the same/case-variant name), not the primary guard.
    __table_args__ = (Index("uq_tags_org_id_name_ci", "org_id", func.lower(name), unique=True),)
