from flask import Blueprint, g, jsonify, request

from api.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from api.container import get_session
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import EmbeddingProviderConfigResponse, EmbeddingProviderConfigUpdateRequest

embedding_settings_bp = Blueprint("embedding_settings", __name__)


def _service() -> EmbeddingProviderConfigService:
    session = get_session()
    return EmbeddingProviderConfigService(
        EmbeddingProviderSettingsRepository(session),
        ChunkRepository(session),
        CategoryRepository(session),
    )


@embedding_settings_bp.get("/embedding-settings")
@require_org_session
def list_embedding_settings():
    statuses = _service().list_status(g.org_id)
    return jsonify([EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json") for status in statuses])


@embedding_settings_bp.get("/embedding-settings/<provider>")
@require_org_session
def get_embedding_settings(provider: str):
    status = _service().get_status(g.org_id, provider)
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.put("/embedding-settings/<provider>")
@require_org_session
def update_embedding_settings(provider: str):
    dto = EmbeddingProviderConfigUpdateRequest.model_validate(request.get_json(silent=True) or {})
    api_key = dto.api_key
    if api_key is None:
        # "Leave blank to keep the current key" — GET /embedding-settings never returns the saved
        # key (only a `configured` boolean), so a caller has no way to round-trip it; omitting
        # api_key must mean "unchanged", not "clear it".
        existing = EmbeddingProviderSettingsRepository(get_session()).get(g.org_id, provider)
        api_key = existing.api_key if existing is not None else None
    status = _service().update_config(
        g.org_id,
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
@require_org_session
def enable_embedding_provider(provider: str):
    status = _service().enable(g.org_id, provider)
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))


@embedding_settings_bp.post("/embedding-settings/<provider>/disable")
@require_org_session
def disable_embedding_provider(provider: str):
    status = _service().disable(g.org_id, provider)
    return jsonify(EmbeddingProviderConfigResponse.from_status(status).model_dump(mode="json"))
