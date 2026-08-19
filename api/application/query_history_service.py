import logging
from uuid import UUID

from api.domain.entities import Query, ScoredChunk
from api.domain.ports import QueryRepositoryPort

logger = logging.getLogger(__name__)


class QueryHistoryService:
    """Best-effort persistence of retrieval activity for later analytics (Dashboard's most-
    retrieved-documents table, Item page's retrieval stats) — never raises, mirroring
    CategoryService._sync_description_embedding's "don't let a secondary concern break the
    primary operation" rationale. A query still returning results to the user matters more than
    its history row landing."""

    def __init__(self, repository: QueryRepositoryPort):
        self._repository = repository

    def record(
        self, org_id: UUID, user_id: UUID | None, query_text: str, latency_ms: int, chunks: list[ScoredChunk]
    ) -> None:
        try:
            query = self._repository.create(
                org_id, query_text, user_id=user_id, latency_ms=latency_ms, result_count=len(chunks)
            )
            self._repository.record_results(
                query.id, [(chunk.id, rank, chunk.score) for rank, chunk in enumerate(chunks, start=1)]
            )
        except Exception:
            # A failed flush leaves the request-scoped session's transaction unusable for whatever
            # runs next (including Flask's own commit-on-teardown) unless rolled back here — this
            # write must never be allowed to break the primary operation it's riding alongside.
            self._repository.rollback()
            logger.warning("Failed to record query history", extra={"org_id": str(org_id)}, exc_info=True)

    def list_history(self, org_id: UUID, limit: int, offset: int) -> list[Query]:
        return self._repository.list_by_org(org_id, limit, offset)
