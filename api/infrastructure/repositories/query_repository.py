from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func

from api.domain.entities import Query as QueryEntity
from api.infrastructure.orm import Chunk as ChunkModel
from api.infrastructure.orm import Document as DocumentModel
from api.infrastructure.orm import Query as QueryModel
from api.infrastructure.orm import QueryResult as QueryResultModel


def _to_entity(model: QueryModel) -> QueryEntity:
    return QueryEntity(
        id=model.id,
        org_id=model.org_id,
        user_id=model.user_id,
        query_text=model.query_text,
        latency_ms=model.latency_ms,
        result_count=model.result_count,
        created_at=model.created_at,
    )


class QueryRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, query_text: str, **fields) -> QueryEntity:
        model = QueryModel(org_id=org_id, query_text=query_text, **fields)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def record_results(self, query_id: UUID, results: list[tuple[UUID, int, float]]) -> None:
        """results: (chunk_id, rank, similarity_score) tuples, one per retrieved chunk."""
        for chunk_id, rank, similarity_score in results:
            self._session.add(
                QueryResultModel(query_id=query_id, chunk_id=chunk_id, rank=rank, similarity_score=similarity_score)
            )
        self._session.flush()

    def rollback(self) -> None:
        self._session.rollback()

    def list_by_org(self, org_id: UUID, limit: int, offset: int) -> list[QueryEntity]:
        models = (
            self._session.query(QueryModel)
            .filter(QueryModel.org_id == org_id)
            .order_by(QueryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_to_entity(model) for model in models]

    def count_since(self, org_id: UUID, since: datetime) -> int:
        return (
            self._session.query(QueryModel)
            .filter(QueryModel.org_id == org_id, QueryModel.created_at >= since)
            .count()
        )

    def avg_latency_since(self, org_id: UUID, since: datetime) -> float | None:
        result = (
            self._session.query(func.avg(QueryModel.latency_ms))
            .filter(QueryModel.org_id == org_id, QueryModel.created_at >= since, QueryModel.latency_ms.isnot(None))
            .scalar()
        )
        return float(result) if result is not None else None

    def most_retrieved_documents(self, org_id: UUID, limit: int) -> list[tuple[UUID, str, int, float]]:
        # query_results carries no org_id of its own — org-scoping happens via its parent query,
        # the only place org_id lives on this side of the join.
        rows = (
            self._session.query(
                DocumentModel.id,
                DocumentModel.title,
                func.count(QueryResultModel.id),
                func.avg(QueryResultModel.similarity_score),
            )
            .select_from(QueryResultModel)
            .join(ChunkModel, ChunkModel.id == QueryResultModel.chunk_id)
            .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
            .join(QueryModel, QueryModel.id == QueryResultModel.query_id)
            .filter(QueryModel.org_id == org_id)
            .group_by(DocumentModel.id, DocumentModel.title)
            .order_by(func.count(QueryResultModel.id).desc())
            .limit(limit)
            .all()
        )
        return [(doc_id, title, count, float(avg_similarity)) for doc_id, title, count, avg_similarity in rows]

    def retrieval_stats_for_document(self, document_id: UUID) -> tuple[int, float | None]:
        count, avg_similarity = (
            self._session.query(func.count(QueryResultModel.id), func.avg(QueryResultModel.similarity_score))
            .join(ChunkModel, ChunkModel.id == QueryResultModel.chunk_id)
            .filter(ChunkModel.document_id == document_id)
            .one()
        )
        return (count or 0, float(avg_similarity) if avg_similarity is not None else None)
