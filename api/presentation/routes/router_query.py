from flask import Blueprint, g, jsonify, request

from api.application.category_router_service import CategoryRouterService
from api.application.retrieval_service import RetrievalService
from api.container import get_session
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.category_repository import CategoryRepository
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


@router_query_bp.post("/query")
@require_org_session
def query_all_categories():
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    results = _service().query(g.org_id, dto.query, dto.top_k)
    return jsonify({"chunks": [RoutedScoredChunkResponse.from_entity(result).model_dump(mode="json") for result in results]})
