from datetime import datetime, timedelta, timezone
from uuid import UUID

from api.domain.entities import DashboardStats, MostRetrievedDocument
from api.domain.ports import ChunkRepositoryPort, DocumentRepositoryPort, QueryRepositoryPort

# The dashboard's "last 30 days" window and "top N" cutoff — display choices for this one view,
# not values anything else in the app depends on, so kept local rather than promoted to
# api.constants (same rationale as org_membership_service.py's _SLUG_COLLISION_RETRIES).
_DASHBOARD_WINDOW_DAYS = 30
_MOST_RETRIEVED_LIMIT = 5


class StatsService:
    def __init__(self, documents: DocumentRepositoryPort, chunks: ChunkRepositoryPort, queries: QueryRepositoryPort):
        self._documents = documents
        self._chunks = chunks
        self._queries = queries

    def get_dashboard_stats(self, org_id: UUID) -> DashboardStats:
        since = datetime.now(timezone.utc) - timedelta(days=_DASHBOARD_WINDOW_DAYS)
        most_retrieved = [
            MostRetrievedDocument(document_id=document_id, title=title, retrieval_count=count, avg_similarity=avg_similarity)
            for document_id, title, count, avg_similarity in self._queries.most_retrieved_documents(
                org_id, _MOST_RETRIEVED_LIMIT
            )
        ]
        return DashboardStats(
            document_count=self._documents.count_for_org(org_id),
            chunk_count=self._chunks.count_for_org(org_id),
            queries_last_30d=self._queries.count_since(org_id, since),
            avg_query_latency_ms=self._queries.avg_latency_since(org_id, since),
            most_retrieved_documents=most_retrieved,
        )
