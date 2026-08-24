from flask import Blueprint, g, jsonify, request

from api.application.app_auth_service import AppAuthService
from api.application.mcp_connection_test_service import MCPConnectionTestService
from api.application.mcp_settings_service import MCPSettingsService
from api.application.permission_service import PermissionService
from api.container import get_session
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.mcp_settings_repository import MCPSettingsRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.presentation.routes.app_auth import require_permission
from api.presentation.schemas import (
    MCPConnectionTestRequest,
    MCPConnectionTestResponse,
    MCPSettingsResponse,
    MCPSettingsUpdateRequest,
)

mcp_settings_bp = Blueprint("mcp_settings", __name__)


def _service() -> MCPSettingsService:
    return MCPSettingsService(MCPSettingsRepository(get_session()))


def _connection_test_service() -> MCPConnectionTestService:
    # Independent construction of AppAuthService, same as app_auth.py's require_permission and
    # api/mcp_server/auth.py's KnowledgeTokenVerifier each already do — this app has no shared
    # factory for it, by design (see AppAuthService's own docstring on being framework-free and
    # reusable, not on being wired through one central place).
    session_ = get_session()
    permissions = PermissionService(OrgMemberRepository(session_), ProfileRepository(session_))
    app_auth = AppAuthService(ApplicationRepository(session_), PersonalAccessTokenRepository(session_), permissions)
    return MCPConnectionTestService(app_auth, MCPSettingsRepository(session_))


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


@mcp_settings_bp.post("/mcp-settings/test-connection")
@require_permission("mcp_settings:read")
def test_mcp_connection():
    # Read-only diagnostic (no state change), gated the same as viewing this page — a non-admin
    # who can see a tier's URL should also be able to check whether their own token reaches it,
    # not just an admin with mcp_settings:write.
    dto = MCPConnectionTestRequest.model_validate(request.get_json(silent=True) or {})
    result = _connection_test_service().test(g.org_id, dto.tier, dto.token)
    return jsonify(MCPConnectionTestResponse.from_result(result).model_dump(mode="json"))
