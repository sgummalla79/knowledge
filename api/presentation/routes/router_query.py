import time

from flask import Blueprint, g, jsonify, request

from api.application.category_router_service import CategoryRouterService
from api.application.query_history_service import QueryHistoryService
from api.application.retrieval_service import RetrievalService
from api.container import get_session
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import QueryRequest, RoutedScoredChunkResponse

router_query_bp = Blueprint("router_query", __name__)


def _service() -> CategoryRouterService:
    session = get_session()
    return CategoryRouterService(
        CategoryRepository(session),
        EmbeddingSettingsRepository(session),
        RetrievalService(ChunkRepository(session), EmbeddingSettingsRepository(session)),
    )


def _history_service() -> QueryHistoryService:
    return QueryHistoryService(QueryRepository(get_session()))


@router_query_bp.post("/query")
@require_org_session
def query_all_categories():
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    start = time.monotonic()
    results = _service().query(g.org_id, dto.query, dto.top_k)
    latency_ms = int((time.monotonic() - start) * 1000)
    _history_service().record(g.org_id, g.user_id, dto.query, latency_ms, [result.chunk for result in results])

    document_ids = {result.chunk.document_id for result in results}
    documents = {document.id: document for document in DocumentRepository(get_session()).list_by_ids(list(document_ids))}
    chunks = [
        RoutedScoredChunkResponse.from_entity(
            result,
            document_title=documents[result.chunk.document_id].title if result.chunk.document_id in documents else "",
            document_type=documents[result.chunk.document_id].type if result.chunk.document_id in documents else "",
        ).model_dump(mode="json")
        for result in results
    ]
    return jsonify({"chunks": chunks})
