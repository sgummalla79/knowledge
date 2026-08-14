from flask import Blueprint, jsonify, request

from app.application.router_settings_service import RouterSettingsService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.router_settings_repository import RouterSettingsRepository
from app.presentation.schemas import RouterSettingsResponse, RouterSettingsUpdateRequest

router_settings_bp = Blueprint("router_settings", __name__)


def _service() -> RouterSettingsService:
    return RouterSettingsService(RouterSettingsRepository(get_session()))


@router_settings_bp.get("/router-settings")
@require_scope("router_settings:read")
def get_router_settings():
    settings = _service().get_status()
    return jsonify(RouterSettingsResponse.from_entity(settings).model_dump(mode="json"))


@router_settings_bp.put("/router-settings")
@require_scope("router_settings:write")
def update_router_settings():
    dto = RouterSettingsUpdateRequest.model_validate(request.get_json(silent=True) or {})
    settings = _service().update(dto.top_n, dto.min_similarity)
    return jsonify(RouterSettingsResponse.from_entity(settings).model_dump(mode="json"))
