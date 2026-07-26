import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_id = Column(UUID(as_uuid=True), ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False)
    source_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "library_id": str(self.library_id),
            "source_filename": self.source_filename,
            "file_type": self.file_type,
            "status": self.status,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
