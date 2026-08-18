from flask import Blueprint, jsonify, request

from app.application.category_router_service import CategoryRouterService
from app.application.retrieval_service import RetrievalService
from app import container
from app.container import get_session
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.presentation.schemas import QueryRequest, RoutedScoredChunkResponse

router_query_bp = Blueprint("router_query", __name__)


def _service() -> CategoryRouterService:
    session = get_session()
    return CategoryRouterService(
        CategoryRepository(session),
        EmbeddingSettingsRepository(session),
        RetrievalService(ChunkRepository(session), EmbeddingSettingsRepository(session)),
    )


@router_query_bp.post("/query")
def query_all_categories():
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    results = _service().query(container.get_default_org_id(), dto.query, dto.top_k)
    return jsonify({"chunks": [RoutedScoredChunkResponse.from_entity(result).model_dump(mode="json") for result in results]})
