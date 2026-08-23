from flask import Blueprint, g, jsonify, request

from api.application.session_settings_service import SessionSettingsService
from api.container import get_session
from api.infrastructure.repositories.session_settings_repository import SessionSettingsRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.schemas import SessionSettingsResponse, SessionSettingsUpdateRequest

session_settings_bp = Blueprint("session_settings", __name__)


def _service() -> SessionSettingsService:
    return SessionSettingsService(SessionSettingsRepository(get_session()))


@session_settings_bp.get("/session-settings")
@require_permission("session_settings:read")
def get_session_settings():
    settings = _service().get(g.org_id)
    return jsonify(SessionSettingsResponse.from_entity(settings).model_dump(mode="json"))


@session_settings_bp.put("/session-settings")
@require_permission("session_settings:write")
def update_session_settings():
    dto = SessionSettingsUpdateRequest.model_validate(request.get_json(silent=True) or {})
    settings = _service().update(g.org_id, dto.inactivity_timeout_minutes, g.user_id)
    return jsonify(SessionSettingsResponse.from_entity(settings).model_dump(mode="json"))
