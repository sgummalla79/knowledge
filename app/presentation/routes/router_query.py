from flask import Blueprint, jsonify, request

from app.application.library_router_service import LibraryRouterService
from app.application.retrieval_service import RetrievalService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.infrastructure.repositories.router_settings_repository import RouterSettingsRepository
from app.infrastructure.repositories.search_settings_repository import SearchSettingsRepository
from app.presentation.schemas import QueryRequest, RoutedScoredChunkResponse

router_query_bp = Blueprint("router_query", __name__)


def _service() -> LibraryRouterService:
    session = get_session()
    return LibraryRouterService(
        CategoryRepository(session),
        EmbeddingSettingsRepository(session),
        RouterSettingsRepository(session),
        SearchSettingsRepository(session),
        RetrievalService(
            CategoryRepository(session),
            ChunkRepository(session),
            EmbeddingSettingsRepository(session),
            SearchSettingsRepository(session),
        ),
    )


@router_query_bp.post("/query")
@require_scope("query:execute")
def query_all_libraries():
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    results = _service().query(dto.query, dto.top_k)
    return jsonify({"chunks": [RoutedScoredChunkResponse.from_entity(result).model_dump(mode="json") for result in results]})
