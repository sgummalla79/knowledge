from uuid import UUID

from flask import Blueprint, jsonify, request

from app.application.retrieval_service import RetrievalService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.infrastructure.repositories.search_settings_repository import SearchSettingsRepository
from app.presentation.schemas import QueryRequest, ScoredChunkResponse

query_bp = Blueprint("query", __name__, url_prefix="/libraries/<uuid:library_id>")


def _service() -> RetrievalService:
    session = get_session()
    return RetrievalService(
        CategoryRepository(session),
        ChunkRepository(session),
        EmbeddingSettingsRepository(session),
        SearchSettingsRepository(session),
    )


@query_bp.post("/query")
@require_scope("query:execute")
def query_library(library_id: UUID):
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    chunks = _service().query(library_id, dto.query, dto.top_k)
    return jsonify({"chunks": [ScoredChunkResponse.from_entity(chunk).model_dump(mode="json") for chunk in chunks]})
