from flask import Blueprint, jsonify, request

from app.application.search_settings_service import SearchSettingsService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.search_settings_repository import SearchSettingsRepository
from app.presentation.schemas import SearchSettingsResponse, SearchSettingsUpdateRequest

search_settings_bp = Blueprint("search_settings", __name__)


def _service() -> SearchSettingsService:
    return SearchSettingsService(SearchSettingsRepository(get_session()))


@search_settings_bp.get("/search-settings")
@require_scope("search_settings:read")
def get_search_settings():
    settings = _service().get_status()
    return jsonify(SearchSettingsResponse.from_entity(settings).model_dump(mode="json"))


@search_settings_bp.put("/search-settings")
@require_scope("search_settings:write")
def update_search_settings():
    dto = SearchSettingsUpdateRequest.model_validate(request.get_json(silent=True) or {})
    settings = _service().update(dto.dense_k, dto.sparse_k, dto.rrf_k)
    return jsonify(SearchSettingsResponse.from_entity(settings).model_dump(mode="json"))
