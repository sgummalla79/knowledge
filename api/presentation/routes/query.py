import time
from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.query_history_service import QueryHistoryService
from api.application.retrieval_service import RetrievalService
from api.container import get_session
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.schemas import QueryRequest, ScoredChunkResponse

# Queries one specific category directly, bypassing the router — see router_query.py for the
# "no category specified, auto-route across all of them" counterpart.
query_bp = Blueprint("query", __name__, url_prefix="/categories/<uuid:category_id>")


def _service() -> RetrievalService:
    session = get_session()
    return RetrievalService(ChunkRepository(session), EmbeddingSettingsRepository(session))


def _history_service() -> QueryHistoryService:
    return QueryHistoryService(QueryRepository(get_session()))


@query_bp.post("/query")
@require_permission("queries:execute")
def query_category(category_id: UUID):
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    start = time.monotonic()
    chunks = _service().query(g.org_id, dto.query, dto.top_k, category_id=category_id)
    latency_ms = int((time.monotonic() - start) * 1000)
    _history_service().record(g.org_id, g.user_id, dto.query, latency_ms, chunks)
    return jsonify({"chunks": [ScoredChunkResponse.from_entity(chunk).model_dump(mode="json") for chunk in chunks]})
