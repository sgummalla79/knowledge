from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
