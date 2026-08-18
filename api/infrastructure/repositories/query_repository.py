from __future__ import annotations

from uuid import UUID

from api.domain.entities import Query as QueryEntity
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
