import logging
import re
import uuid

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.config import config
from app.constants import DEFAULT_TOP_K, SCOPE_LIBRARIES_READ, SCOPE_QUERY_EXECUTE
from app.infrastructure.auth.redirect_uri import is_loopback_host
from app.logging_config import configure_logging, reset_request_id, set_request_id
from mcp_server.client import RagApiClient

configure_logging(config.log_level)
logger = logging.getLogger(__name__)

_JWT_ALGORITHM = "HS256"


class KnowledgeApiTokenVerifier(TokenVerifier):
    """Validates the same JWTs knowledge-api's own /oauth/token issues. Decodes directly with
    PyJWT (not app.infrastructure.auth.jwt_tokens.decode_access_token) since that helper reads the
    signing key off Flask's `current_app`, and this process is a standalone MCP server, never a
    Flask request."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(token, config.secret_key, algorithms=[_JWT_ALGORITHM])
        except jwt.InvalidTokenError:
            return None
        return AccessToken(
            token=token,
            client_id=claims["sub"],
            scopes=claims.get("scope", "").split(),
            expires_at=int(claims["exp"]),
        )


mcp = FastMCP(
    "rag-knowledge",
    # 0.0.0.0 *inside the container* — matches how gunicorn itself binds (app/__init__.py runs
    # under the same container). A process bound to 127.0.0.1 inside a container is unreachable
    # through Docker's port publishing at all (it's a different network namespace's loopback), so
    # binding narrowly here wouldn't add safety, only breakage. "Never reachable off this machine"
    # is enforced one layer out instead, by deploy/docker-compose.yml's host-side port mapping
    # (`127.0.0.1:${MCP_HTTP_PORT}:${MCP_HTTP_PORT}`), same as it would be for any other service.
    host="0.0.0.0",
    port=config.mcp_http_port,
    streamable_http_path="/mcp",
    auth=AuthSettings(
        # knowledge-api's Flask app is the authorization server (POST /oauth/authorize,
        # /oauth/token, /oauth/register, /.well-known/oauth-authorization-server all live there);
        # this process only ever verifies the tokens it issues, via KnowledgeApiTokenVerifier.
        issuer_url=f"http://127.0.0.1:{config.port}",
        resource_server_url=f"http://127.0.0.1:{config.mcp_http_port}/mcp",
        required_scopes=[SCOPE_LIBRARIES_READ, SCOPE_QUERY_EXECUTE],
    ),
    token_verifier=KnowledgeApiTokenVerifier(),
)
_client = RagApiClient()

_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource" + mcp.settings.streamable_http_path


def _loopback_request_host(host_header: str | None) -> str | None:
    if not host_header:
        return None
    hostname = host_header.split(":", 1)[0]
    return host_header if is_loopback_host(hostname) else None


async def _protected_resource_metadata(request: Request) -> JSONResponse:
    # The mcp SDK (pinned mcp==1.27.0) bakes a single, fixed resource_server_url/issuer_url into
    # this document once, at process startup. RFC 9728 requires the `resource` field to match
    # whatever host the client actually connected with, so a client that reaches this server via a
    # different (but equally valid) loopback hostname than the one baked in — "localhost" vs
    # "127.0.0.1" — fails that check; separately, if the client's browser session with the
    # dashboard was established under one of those hostnames, sending it to `authorization_servers`
    # under the *other* one looks logged-out (session cookies don't cross hostnames even on the
    # same machine). This route shadows the SDK's static one (see __main__ below) and echoes back
    # whichever recognized loopback host the request actually used for both fields — same hostname
    # as the request, but knowledge-api's own port (`config.port`) for `authorization_servers`,
    # since that's a different process on a different port. Any other Host header (never
    # legitimate for a loopback-only server) falls back to the static configured URLs rather than
    # being reflected back unchecked.
    host = _loopback_request_host(request.headers.get("host"))
    if host:
        hostname = host.split(":", 1)[0]
        resource = f"{request.url.scheme}://{host}{mcp.settings.streamable_http_path}"
        authorization_servers = [f"{request.url.scheme}://{hostname}:{config.port}/"]
    else:
        resource = str(mcp.settings.auth.resource_server_url)
        authorization_servers = [str(mcp.settings.auth.issuer_url)]
    return JSONResponse(
        {
            "resource": resource,
            "authorization_servers": authorization_servers,
            "scopes_supported": mcp.settings.auth.required_scopes,
            "bearer_methods_supported": ["header"],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _retarget_resource_metadata_host(header_value: bytes, request_host: str) -> bytes:
    text = header_value.decode()
    text = re.sub(r'(resource_metadata="https?://)[^/"]+', rf"\g<1>{request_host}", text)
    return text.encode()


class _RewriteResourceMetadataHost:
    """The same fixed-host problem shows up in the 401 response's WWW-Authenticate header: its
    `resource_metadata` URL is baked into the mcp SDK's auth middleware at startup, not derived
    per-request. This ASGI middleware rewrites that URL's host to match the incoming request's own
    Host header, restricted to recognized loopback hostnames (never reflects an arbitrary
    attacker-supplied Host header — not that it would matter much given this port is only ever
    reachable from this machine to begin with, see deploy/docker-compose.yml)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        host_header = next((value for key, value in scope["headers"] if key == b"host"), b"").decode() or None
        request_host = _loopback_request_host(host_header)

        async def send_wrapper(message):
            if request_host and message["type"] == "http.response.start":
                message["headers"] = [
                    (key, _retarget_resource_metadata_host(value, request_host) if key == b"www-authenticate" else value)
                    for key, value in message["headers"]
                ]
            await send(message)

        await self.app(scope, receive, send_wrapper)


@mcp.tool()
def list_libraries() -> list[dict]:
    """List all available knowledge libraries and their metadata."""
    token = set_request_id(str(uuid.uuid4())[:8])
    try:
        logger.info("MCP tool call: list_libraries")
        return _client.list_libraries()
    finally:
        reset_request_id(token)


@mcp.tool()
def query_library(library_id: str, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Retrieve the most relevant chunks from a knowledge library for a query."""
    token = set_request_id(str(uuid.uuid4())[:8])
    try:
        logger.info(
            "MCP tool call: query_library", extra={"library_id": library_id, "top_k": top_k}
        )
        return _client.query_library(library_id, query, top_k)
    finally:
        reset_request_id(token)


if __name__ == "__main__":
    import uvicorn

    app = mcp.streamable_http_app()
    # Shadows the SDK's own static protected-resource-metadata route (registered at the same
    # path, later in the list) — Starlette's router uses the first matching route.
    app.router.routes.insert(0, Route(_RESOURCE_METADATA_PATH, endpoint=_protected_resource_metadata, methods=["GET"]))

    uvicorn.run(
        _RewriteResourceMetadataHost(app),
        host=mcp.settings.host,
        port=mcp.settings.port,
        log_level=mcp.settings.log_level.lower(),
    )
