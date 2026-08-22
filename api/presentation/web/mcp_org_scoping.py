import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from api.application.app_auth_service import AppAuthService
from api.application.permission_service import PermissionService
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.mcp_server.db import session_scope

# Every org's MCP tools live at /<org-slug>/mcp/<tier> — never the bare /mcp/<tier>, even though
# that's still the literal path FastMCP itself serves internally (see mcp_server/server.py's fixed
# streamable_http_path). Deliberately NOT made org-slug-aware there: FastMCP's streamable-http path
# doubles as its RFC 9728 well-known discovery route, computed relative to that path — nesting or
# templating it already broke once (see asgi_bridge.py's build_asgi_app docstring) and re-touching
# it for this would risk the same class of bug again.
#
# Instead, this is a thin ASGI layer in front of the merged app: resolve the URL's org slug, reject
# a request whose bearer token belongs to a *different* org (or has none) before it ever reaches
# FastMCP, then rewrite the path down to the bare /mcp/<tier> FastMCP actually matches and forward.
# The bare path is rejected outright when hit directly — there must be exactly one valid URL per
# tier per org, not a second one that skips the org check.
_ORG_SCOPED_PATH = re.compile(r"^/(?P<org_slug>[^/]+)/mcp/(?P<tier>rag|read|write)(?P<rest>/.*)?$")
_BARE_MCP_PATH = re.compile(r"^/mcp/(rag|read|write)(/.*)?$")


def _bearer_token(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            text = value.decode("latin-1")
            if text.startswith("Bearer "):
                return text[len("Bearer ") :]
    return None


async def _reject(scope: Scope, receive: Receive, send: Send, status_code: int, message: str) -> None:
    response = JSONResponse({"error": {"message": message}}, status_code=status_code)
    await response(scope, receive, send)


class MCPOrgScopingMiddleware:
    """Wraps the combined Flask+MCP ASGI app (see asgi_bridge.build_asgi_app) — pure ASGI, not
    Starlette's BaseHTTPMiddleware, since MCP's streamable-http transport holds long-lived
    streaming connections that BaseHTTPMiddleware's response buffering would interfere with."""

    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self._app(scope, receive, send)

        path = scope["path"]
        match = _ORG_SCOPED_PATH.match(path)
        if match is None:
            if _BARE_MCP_PATH.match(path):
                return await _reject(scope, receive, send, 404, "Not found.")
            return await self._app(scope, receive, send)

        org_slug = match.group("org_slug")
        tier = match.group("tier")
        rest = match.group("rest") or ""

        token = _bearer_token(scope)
        if token is None:
            return await _reject(scope, receive, send, 401, "Not authenticated.")

        with session_scope() as session:
            organization = OrganizationRepository(session).get_by_slug(org_slug)
            if organization is None:
                return await _reject(scope, receive, send, 404, "Not found.")
            auth_service = AppAuthService(
                ApplicationRepository(session),
                PersonalAccessTokenRepository(session),
                PermissionService(OrgMemberRepository(session), ProfileRepository(session)),
            )
            caller = auth_service.authenticate_bearer_token(token)

        if caller is None or caller.org_id != organization.id:
            return await _reject(scope, receive, send, 403, "This credential does not belong to this organization.")

        rewritten_scope = dict(scope)
        rewritten_scope["path"] = f"/mcp/{tier}{rest}"
        rewritten_scope["raw_path"] = rewritten_scope["path"].encode("utf-8")
        return await self._app(rewritten_scope, receive, send)
