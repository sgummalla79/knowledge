from flask import Blueprint, g, jsonify, request

from api.application.mcp_settings_service import MCPSettingsService
from api.container import get_session
from api.infrastructure.repositories.mcp_settings_repository import MCPSettingsRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.schemas import MCPSettingsResponse, MCPSettingsUpdateRequest

mcp_settings_bp = Blueprint("mcp_settings", __name__)


def _service() -> MCPSettingsService:
    return MCPSettingsService(MCPSettingsRepository(get_session()))


@mcp_settings_bp.get("/mcp-settings")
@require_permission("mcp_settings:read")
def get_mcp_settings():
    settings = _service().get(g.org_id)
    return jsonify(MCPSettingsResponse.from_entity(settings).model_dump(mode="json"))


@mcp_settings_bp.put("/mcp-settings")
@require_permission("mcp_settings:write")
def update_mcp_settings():
    dto = MCPSettingsUpdateRequest.model_validate(request.get_json(silent=True) or {})
    settings = _service().update(
        g.org_id, dto.search_read_enabled, dto.object_read_enabled, dto.object_write_enabled, g.user_id
    )
    return jsonify(MCPSettingsResponse.from_entity(settings).model_dump(mode="json"))
