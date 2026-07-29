from flask import Blueprint, jsonify, request

from app.application.embedding_provider_settings_service import EmbeddingProviderSettingsService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.presentation.schemas import EmbeddingProviderToggleResponse, EmbeddingProviderToggleUpdateRequest

embedding_provider_settings_bp = Blueprint("embedding_provider_settings", __name__)


def _service() -> EmbeddingProviderSettingsService:
    return EmbeddingProviderSettingsService(EmbeddingProviderSettingsRepository(get_session()))


@embedding_provider_settings_bp.get("/embedding-provider-settings")
@require_scope("embedding_settings:read")
def list_embedding_provider_settings():
    toggles = _service().list_providers()
    return jsonify([EmbeddingProviderToggleResponse.from_entity(toggle).model_dump(mode="json") for toggle in toggles])


@embedding_provider_settings_bp.put("/embedding-provider-settings/<provider>")
@require_scope("embedding_settings:write")
def update_embedding_provider_setting(provider: str):
    dto = EmbeddingProviderToggleUpdateRequest.model_validate(request.get_json(silent=True) or {})
    toggle = _service().set_enabled(provider, dto.enabled)
    return jsonify(EmbeddingProviderToggleResponse.from_entity(toggle).model_dump(mode="json"))
