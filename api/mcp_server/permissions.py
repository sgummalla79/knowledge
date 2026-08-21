from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp.exceptions import ToolError

from api.infrastructure.repositories.mcp_settings_repository import MCPSettingsRepository

# One tool-tier name per mounted MCP endpoint (/mcp/rag, /mcp/read, /mcp/write) — see
# mcp_server/server.py — mapped to the mcp_settings column an org admin toggles to activate it.
_TIER_SETTINGS_COLUMN = {
    "rag": "rag_read_enabled",
    "read": "object_read_enabled",
    "write": "object_write_enabled",
}


def current_caller() -> dict:
    """The MCP-tool-call counterpart to api/presentation/routes/app_auth.py's g.org_id/g.user_id —
    reads the AccessToken (and its claims) KnowledgeTokenVerifier resolved for this connection."""
    access_token = get_access_token()
    if access_token is None:
        raise ToolError("Not authenticated.")
    claims = access_token.claims or {}
    return {
        "org_id": UUID(claims["org_id"]),
        "identity_id": UUID(claims["identity_id"]),
        "application_id": UUID(access_token.client_id),
        "scopes": frozenset(access_token.scopes),
        "mcp_access": bool(claims.get("mcp_access", False)),
    }


def require_tier_permission(session, tier: str, permission: str | None) -> dict:
    """Every tool calls this first — three independent gates, cheapest-to-most-expensive:

    1. This application has mcp_access at all (read straight off the AccessToken claims already
       resolved by KnowledgeTokenVerifier — no DB round trip).
    2. This tool's tier (rag/read/write) is activated for the caller's org (mcp_settings — one DB
       row read).
    3. If a permission is given, the caller's already-resolved scopes grant it — the exact same
       `caller.scopes` AppAuthService.authenticate_bearer_token resolved fresh for this request
       (the execute-as identity's profile for client_credentials/authorization_code, the owning
       identity's profile for a personal access token), so this checks the identical vocabulary
       require_permission's HTTP-side counterpart already checks — no separate profile
       re-resolution needed here.

    All three independent: a permissive profile doesn't help if the tier is off org-wide, and an
    active tier doesn't help an application without mcp_access."""
    caller = current_caller()
    if not caller["mcp_access"]:
        raise ToolError("This application does not have MCP access.")

    settings = MCPSettingsRepository(session).get(caller["org_id"])
    tier_enabled = getattr(settings, _TIER_SETTINGS_COLUMN[tier]) if settings is not None else False
    if not tier_enabled:
        raise ToolError(f"The '{tier}' MCP tool tier is not enabled for this organization.")

    if permission is not None and permission not in caller["scopes"]:
        raise ToolError(f"This application is not authorized for permission '{permission}'.")

    return caller
