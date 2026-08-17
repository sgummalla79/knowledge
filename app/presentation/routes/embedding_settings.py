from flask import Blueprint, jsonify, request

from app.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.presentation.schemas import EmbeddingProviderConfigResponse, EmbeddingProviderConfigUpdateRequest

embedding_settings_bp = Blueprint("embedding_settings", __name__)


def _service() -> EmbeddingProviderConfigService:
    session = get_session()
    return EmbeddingProviderConfigService(
        EmbeddingProviderSettingsRepository(session),
        ChunkRepository(session),
        CategoryRepository(session),
    )


@embedding_settings_bp.get("/embedding-settings")
@require_scope("embedding_settings:read")
def list_embedding_settings():
    statuses = _service().list_status()
    return jsonify([EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json") for status in statuses])


@embedding_settings_bp.get("/embedding-settings/<provider>")
@require_scope("embedding_settings:read")
def get_embedding_settings(provider: str):
    status = _service().get_status(provider)
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.put("/embedding-settings/<provider>")
@require_scope("embedding_settings:write")
def update_embedding_settings(provider: str):
    dto = EmbeddingProviderConfigUpdateRequest.model_validate(request.get_json(silent=True) or {})
    api_key = dto.api_key
    if api_key is None:
        # "Leave blank to keep the current key" — GET /embedding-settings never returns the saved
        # key (only a `configured` boolean), so a caller has no way to round-trip it; omitting
        # api_key must mean "unchanged", not "clear it".
        existing = EmbeddingProviderSettingsRepository(get_session()).get(provider)
        api_key = existing.api_key if existing is not None else None
    status = _service().update_config(
        provider,
        dto.model,
        api_key,
        dto.base_url,
        dto.dimensions,
        dto.chunk_size,
        dto.chunk_overlap,
    )
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.post("/embedding-settings/<provider>/enable")
@require_scope("embedding_settings:write")
def enable_embedding_provider(provider: str):
    status = _service().enable(provider)
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.post("/embedding-settings/<provider>/disable")
@require_scope("embedding_settings:write")
def disable_embedding_provider(provider: str):
    status = _service().disable(provider)
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))
