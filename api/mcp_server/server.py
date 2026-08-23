from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from api.mcp_server.auth import KnowledgeTokenVerifier
from api.mcp_server.config import config
from api.mcp_server.tools import read as read_tools
from api.mcp_server.tools import search as search_tools
from api.mcp_server.tools import write as write_tools

# Three non-overlapping tool tiers, each its own FastMCP instance (own tool registry, own
# resource_server_url) sharing one KnowledgeTokenVerifier — auth resolution is identical across
# tiers, only the tier name each tool passes to require_tier_permission differs. Mounted at
# /mcp/search, /mcp/read, /mcp/write by api/asgi.py — see build_asgi_app's lifespan handling for
# why each server's session_manager needs to be entered there, not here.
_TIERS = {
    "search": (search_tools, "Search and browse a connected org's knowledge base."),
    "read": (read_tools, "Read a connected org's shelves, documents, tags, and embedding model config."),
    "write": (write_tools, "Create and modify a connected org's documents, categories, shelves, and tags."),
}


def _create_tier_server(tier: str, register, instructions: str) -> FastMCP:
    mcp = FastMCP(
        name=f"knowledge-{tier}",
        instructions=instructions,
        token_verifier=KnowledgeTokenVerifier(),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(config.base_url),
            resource_server_url=AnyHttpUrl(f"{config.base_url}/mcp/{tier}"),
        ),
        # The SDK builds this server's own Starlette app (streamable_http_app(), called by
        # api.presentation.web.asgi_bridge.build_asgi_app) with the streamable-http endpoint at
        # exactly this path AND its RFC 9728 well-known discovery route computed relative to the
        # *same* app root from resource_server_url above — both need to be full, real top-level
        # paths, not "/", since build_asgi_app merges this server's routes directly into the
        # combined app rather than nesting it under an extra Mount (nesting would double the path
        # and break the well-known route's path-insertion).
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
