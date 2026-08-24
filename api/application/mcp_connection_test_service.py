from uuid import UUID

from api.application.app_auth_service import AppAuthService
from api.constants import MCP_TIERS
from api.domain.entities import MCPConnectionTestResult
from api.domain.ports import MCPSettingsRepositoryPort

# URL segment (e.g. "search") -> mcp_settings enabled-column (e.g. "search_read_enabled"), the
# reverse direction of MCPSettingsResponse's tier_url_segments — same MCP_TIERS source
# api/mcp_server/permissions.py's own reverse mapping derives from, so this can't drift from it.
_TIER_COLUMN_BY_SEGMENT = {segment: column for column, segment in MCP_TIERS}


class MCPConnectionTestService:
    """Dry-runs the same gate chain a real MCP request goes through —
    api/presentation/web/mcp_org_scoping.py's token/org check, then
    api/mcp_server/permissions.py's require_tier_permission's mcp_access/tier-enabled checks —
    without opening a real MCP/streamable-http session. Lets Settings > MCP's "Test connection"
    button tell a user exactly which gate a token would fail at, rather than a client-side SDK
    stack trace with no indication of which of the three independent checks actually failed.

    Deliberately does not check any individual tool's own required permission scope (those vary
    per tool within a tier, e.g. documents:write vs categories:write inside the object-write
    tier) — this answers "would the connection itself succeed," the same coarse question
    mcp_org_scoping's own checks answer, not "would every tool in this tier work."
    """

    def __init__(self, app_auth: AppAuthService, mcp_settings: MCPSettingsRepositoryPort):
        self._app_auth = app_auth
        self._mcp_settings = mcp_settings

    def test(self, org_id: UUID, tier_segment: str, token: str) -> MCPConnectionTestResult:
        column = _TIER_COLUMN_BY_SEGMENT.get(tier_segment)
        if column is None:
            return MCPConnectionTestResult(False, "unknown_tier", f"Unknown MCP tier '{tier_segment}'.")

        caller = self._app_auth.authenticate_bearer_token(token)
        if caller is None:
            return MCPConnectionTestResult(False, "invalid_token", "This token is invalid, expired, or revoked.")

        if caller.org_id != org_id:
            return MCPConnectionTestResult(False, "wrong_org", "This token belongs to a different organization.")

        if not caller.mcp_access:
            return MCPConnectionTestResult(
                False, "no_mcp_access", "This token does not have MCP access enabled."
            )

        settings = self._mcp_settings.get(org_id)
        tier_enabled = getattr(settings, column) if settings is not None else False
        if not tier_enabled:
            return MCPConnectionTestResult(
                False, "tier_disabled", "This tier is not enabled for this organization yet."
            )

        return MCPConnectionTestResult(
            True, "ok", "This token can connect to this tier. Individual tools may still need their own permission."
        )
