from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from api.infrastructure.orm.base import Base


class DocumentShelf(Base):
    __tablename__ = "document_shelves"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    shelf_id = Column(UUID(as_uuid=True), ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True)
