from flask import Blueprint, jsonify, request

from app.application.embedding_settings_service import EmbeddingSettingsService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.presentation.schemas import EmbeddingSettingsResponse, EmbeddingSettingsUpdateRequest

embedding_settings_bp = Blueprint("embedding_settings", __name__)


def _service() -> EmbeddingSettingsService:
    return EmbeddingSettingsService(EmbeddingSettingsRepository(get_session()))


@embedding_settings_bp.get("/embedding-settings")
@require_scope("embedding_settings:read")
def get_embedding_settings():
    status = _service().get_status()
    return jsonify(EmbeddingSettingsResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.put("/embedding-settings")
@require_scope("embedding_settings:write")
def update_embedding_settings():
    dto = EmbeddingSettingsUpdateRequest.model_validate(request.get_json(silent=True) or {})
    status = _service().update(dto.provider, dto.model, dto.api_key, dto.chunk_size, dto.chunk_overlap)
    return jsonify(EmbeddingSettingsResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.delete("/embedding-settings")
@require_scope("embedding_settings:write")
def delete_embedding_settings():
    status = _service().clear()
    return jsonify(EmbeddingSettingsResponse.from_status(status).model_dump(mode="json"))
