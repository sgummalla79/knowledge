from mcp.server.fastmcp import FastMCP

from api.mcp_server.tools import read as read_tools
from api.mcp_server.tools import search as search_tools
from api.mcp_server.tools import write as write_tools

# Three non-overlapping tool tiers, each its own FastMCP instance (own tool registry) — none of
# them do their own auth (see _create_tier_server's docstring below); auth resolution is identical
# across tiers regardless, only the tier name each tool passes to require_tier_permission differs.
# Mounted at /mcp/search, /mcp/read, /mcp/write by api/asgi.py — see build_asgi_app's lifespan
# handling for why each server's session_manager needs to be entered there, not here.
_TIERS = {
    "search": (search_tools, "Search and browse a connected org's knowledge base."),
    "read": (read_tools, "Read a connected org's shelves, documents, tags, and embedding model config."),
    "write": (write_tools, "Create and modify a connected org's documents, categories, shelves, and tags."),
}


def _create_tier_server(tier: str, register, instructions: str) -> FastMCP:
    mcp = FastMCP(
        name=f"knowledge-{tier}",
        instructions=instructions,
        # Deliberately no token_verifier/auth=AuthSettings(...) here. FastMCP's own AuthSettings
        # would add its RFC 9728 protected-resource-metadata route unauthenticated at this shared
        # origin, pointing any MCP client at this app's own OAuth authorization-server metadata —
        # and since that metadata never advertised a registration_endpoint (see oauth.py's
        # discovery route), spec-compliant clients that probe for OAuth before ever sending a
        # configured static bearer header (e.g. Claude Code) refuse to connect at all, with
        # "Incompatible auth server: does not support dynamic client registration". Bearer-token
        # verification instead happens exclusively in api.presentation.web.mcp_org_scoping's
        # MCPOrgScopingMiddleware, which every request already passes through first and which sets
        # auth_context_var itself (mirroring what mcp.server.auth's own AuthContextMiddleware would
        # have done) so mcp_server/permissions.py's current_caller() keeps working unchanged.
        streamable_http_path=f"/mcp/{tier}",
    )
    register(mcp)
    return mcp


def build_mcp_servers() -> list[FastMCP]:
    """One FastMCP instance per tier, each already carrying its own full external path (see
    streamable_http_path above) — ready for api/asgi.py to merge into the combined app and to
    enter each server's session_manager.run() in that app's lifespan."""
    return [
        _create_tier_server(tier, tools_module.register, instructions)
        for tier, (tools_module, instructions) in _TIERS.items()
    ]
