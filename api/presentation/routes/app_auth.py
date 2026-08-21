from functools import wraps
from uuid import UUID

from flask import g, request, session

from api.application.app_auth_service import AppAuthService
from api.application.permission_service import PermissionService
from api.container import get_session, set_rls_session_vars
from api.domain.errors import AuthenticationError, ForbiddenError
from api.infrastructure.repositories.application_api_key_repository import ApplicationApiKeyRepository
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository


def _permission_service() -> PermissionService:
    session_ = get_session()
    return PermissionService(OrgMemberRepository(session_), ProfileRepository(session_))


def _app_auth_service() -> AppAuthService:
    session_ = get_session()
    return AppAuthService(ApplicationRepository(session_), ApplicationApiKeyRepository(session_), _permission_service())


def require_permission(permission: str):
    """Gates a resource route for both a human (session cookie) and a machine caller (an
    application's bearer token), checking `permission` either way — the single unified gate every
    JSON API route uses now, including org-member/application/profile management, not just
    content routes.

    Humans are resolved via their org membership's profile (PermissionService) — this is the
    first time a session request is actually checked against a specific permission at all; before
    profiles existed, any authenticated member could reach any mutating route. Bearer tokens
    resolve via AppAuthService, which tries a client_credentials-issued JWT (permissions from the
    execute-as identity's profile, via PermissionService) before falling back to an api_key
    (Phase 1, checked against the application's own application_scopes, deliberately not migrated
    to profiles — see api/application/permission_service.py's docstring).

    Routes whose URL includes an `org_id` path parameter (e.g. orgs.py's member-management
    routes) are checked against *that* org, not the caller's active/token org — a human can
    administer an org they're not currently "active" in, and a bearer-token caller is naturally
    restricted to its own org since it has no membership anywhere else. Routes without an
    `org_id` kwarg (the common case) are checked against the resolved org as usual.

    Bearer-token callers also need `caller.api_access` set — a channel flag on the application
    itself (mirrors `mcp_access`'s gate on the MCP side), checked before the scope/permission
    check so a caller without it is rejected regardless of what its scopes/profile would otherwise
    allow. Not applicable to session (human) callers, which have no `api_access` concept."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            target_org_id: UUID | None = kwargs.get("org_id")

            if session.get("identity_id") and session.get("active_org_id"):
                user_id = UUID(session["identity_id"])
                org_id = target_org_id or UUID(session["active_org_id"])
                g.user_id = user_id
                g.org_id = org_id
                set_rls_session_vars(org_id, user_id)
                granted = _permission_service().resolve_permissions(user_id, org_id)
                if permission not in granted:
                    raise ForbiddenError(f"You don't have the '{permission}' permission in this organization.")
                return view(*args, **kwargs)

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise AuthenticationError("Not authenticated.")
            caller = _app_auth_service().authenticate_bearer_token(auth_header[len("Bearer ") :])
            if caller is None:
                raise AuthenticationError("Invalid or missing API key.")
            if not caller.api_access:
                raise ForbiddenError("This application does not have REST API access.")
            if target_org_id is not None and target_org_id != caller.org_id:
                raise ForbiddenError("This application does not belong to that organization.")
            if permission not in caller.scopes:
                raise ForbiddenError(f"This application is not authorized for permission '{permission}'.")

            g.org_id = caller.org_id
            g.user_id = caller.identity_id
            set_rls_session_vars(g.org_id, g.user_id)
            return view(*args, **kwargs)

        return wrapped

    return decorator
