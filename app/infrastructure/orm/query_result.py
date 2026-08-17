from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class QueryResult(Base):
    __tablename__ = "query_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    rank = Column(Integer, nullable=False)
    similarity_score = Column(Float, nullable=False)
