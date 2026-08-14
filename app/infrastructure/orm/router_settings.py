import uuid

from sqlalchemy import Column, DateTime, Float, Integer, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class RouterSettings(Base):
    __tablename__ = "router_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    top_n = Column(Integer, nullable=False)
    min_similarity = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
