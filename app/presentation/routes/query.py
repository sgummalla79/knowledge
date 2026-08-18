from uuid import UUID

from flask import Blueprint, jsonify, request

from app import container
from app.application.retrieval_service import RetrievalService
from app.container import get_session
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.presentation.schemas import QueryRequest, ScoredChunkResponse

# Queries one specific category directly, bypassing the router — see router_query.py for the
# "no category specified, auto-route across all of them" counterpart.
query_bp = Blueprint("query", __name__, url_prefix="/categories/<uuid:category_id>")


def _service() -> RetrievalService:
    session = get_session()
    return RetrievalService(ChunkRepository(session), EmbeddingSettingsRepository(session))


@query_bp.post("/query")
def query_category(category_id: UUID):
    dto = QueryRequest.model_validate(request.get_json(silent=True) or {})
    chunks = _service().query(container.get_default_org_id(), dto.query, dto.top_k, category_id=category_id)
    return jsonify({"chunks": [ScoredChunkResponse.from_entity(chunk).model_dump(mode="json") for chunk in chunks]})
