from mcp.server.auth.provider import AccessToken

from api.application.app_auth_service import AppAuthService
from api.application.permission_service import PermissionService
from api.infrastructure.repositories.application_api_key_repository import ApplicationApiKeyRepository
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.mcp_server.db import session_scope


class KnowledgeTokenVerifier:
    """Satisfies mcp.server.auth.provider.TokenVerifier by shape (a Protocol, not an ABC — same
    structural-typing convention this app's own domain/ports.py already uses). Delegates straight
    to AppAuthService.authenticate_bearer_token — the exact function every HTTP route's
    require_permission decorator already uses — so a connected application authenticates
    identically whether it's calling the REST API or an MCP tool, across all three auth methods.

    org_id/identity_id ride in AccessToken.claims (an untyped extension dict the SDK provides for
    exactly this): client_id/scopes alone have nowhere to carry which org a token belongs to."""

    async def verify_token(self, token: str) -> AccessToken | None:
        with session_scope() as session:
            permissions = PermissionService(OrgMemberRepository(session), ProfileRepository(session))
            auth_service = AppAuthService(
                ApplicationRepository(session), ApplicationApiKeyRepository(session), permissions
            )
            caller = auth_service.authenticate_bearer_token(token)
            if caller is None:
                return None
            return AccessToken(
                token=token,
                client_id=str(caller.application_id),
                scopes=sorted(caller.scopes),
                claims={
                    "org_id": str(caller.org_id),
                    "identity_id": str(caller.identity_id),
                    "auth_method": caller.auth_method,
                    "mcp_access": caller.mcp_access,
                },
            )
