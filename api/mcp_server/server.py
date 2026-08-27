from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from api.config import config
from api.mcp_server.tools import read as read_tools
from api.mcp_server.tools import search as search_tools
from api.mcp_server.tools import write as write_tools

# FastMCP only auto-enables its DNS-rebinding Host/Origin check when constructed with
# host="127.0.0.1"/"localhost"/"::1" (its own default, unrelated to where this app actually runs)
# — and when it does, it hardcodes allowed_hosts to localhost/127.0.0.1 wildcards only. Behind a
# reverse proxy (e.g. this repo's Hostinger Traefik ingress) the Host header the container
# actually receives is the real external domain, which never matches those wildcards, so every
# request 421s with "Invalid Host header". Build the settings explicitly instead so the same
# localhost wildcards still apply for local dev/testing, plus whatever real host(s)
# MCP_ALLOWED_HOSTS configures for a given deployment (api/config.py, api/constants.py).
_LOCALHOST_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
_LOCALHOST_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
_TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[*_LOCALHOST_HOSTS, *config.mcp_allowed_hosts],
    allowed_origins=[*_LOCALHOST_ORIGINS, *(f"https://{host}" for host in config.mcp_allowed_hosts)],
)

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
        transport_security=_TRANSPORT_SECURITY,
        # Stateful streamable-http (the default) tracks each session's transport in an in-memory
        # dict scoped to one process — fine for a single worker/replica, broken the moment there's
        # more than one (this deployment runs 3 gunicorn workers x 2 k8s replicas, api/deploy/
        # entrypoint.sh/api/deploy/k3s/02-api.yaml). A follow-up request carrying a session id
        # minted by one process has no guarantee of landing back on that same process — Traefik's
        # own connection pooling to the backend Service doesn't preserve per-client affinity across
        # requests even when the client reuses one connection to Traefik itself — so roughly 5 out
        # of 6 follow-up calls hit a process that never saw the session and reject it with a 404
        # "Session not found" (confirmed empirically: repeated tools/list calls against a real
        # initialize'd session flip-flopped 200/404 in production). stateless_http=True makes every
        # request self-contained (a fresh transport per request, no session id required at all),
        # trading away SSE resumability and idle-session cleanup — neither in use here — for
        # correctness under this multi-process topology with no sticky routing or shared session
        # store configured.
        stateless_http=True,
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
