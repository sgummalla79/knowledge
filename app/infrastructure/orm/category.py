import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_categories_org_id_slug"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # Dimensionless, no HNSW index — same rationale as libraries.description_embedding before it
    # (migration 0017): small counts, sequential scan is trivial, dimension-safety enforced in
    # application code rather than the schema. Nothing reads/writes this yet.
    description_embedding = Column(Vector(), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
