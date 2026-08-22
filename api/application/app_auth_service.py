from uuid import UUID

from api.application.permission_service import PermissionService
from api.domain.entities import ResolvedCaller
from api.domain.ports import ApplicationRepositoryPort, PersonalAccessTokenRepositoryPort
from api.infrastructure.auth.jwt_tokens import decode_access_token
from api.infrastructure.auth.token_hashing import hash_token


class AppAuthService:
    """Resolves a machine caller's bearer token to who it is and what it's allowed to do.
    Deliberately framework-free (no Flask imports) so this exact logic is reusable, unmodified, by
    both the Flask require_permission decorator (api/presentation/routes/app_auth.py) and
    api/mcp_server/ — no duplicated auth logic between the two.

    Two independent verification paths, both resolving permissions the identical way — via
    PermissionService.resolve_permissions(identity_id, org_id), the same function every human
    session request goes through: a client_credentials-issued JWT (the execute-as identity's
    profile) and a personal access token (its owning identity's profile). Neither path keeps its
    own separate scopes table — that model (Connected Applications' old api_key method) was
    removed; see api/application/personal_access_token_service.py for the self-service
    replacement."""

    def __init__(
        self,
        applications: ApplicationRepositoryPort,
        personal_tokens: PersonalAccessTokenRepositoryPort,
        permissions: PermissionService,
    ):
        self._applications = applications
        self._personal_tokens = personal_tokens
        self._permissions = permissions

    def _authenticate_jwt(self, token: str) -> ResolvedCaller | None:
        claims = decode_access_token(token)
        if claims is None:
            return None
        application = self._applications.get(UUID(claims["sub"]))
        if application is None or application.status != "active":
            return None
        identity_id = UUID(claims["identity_id"])
        granted = self._permissions.resolve_permissions(identity_id, application.org_id)
        return ResolvedCaller(
            org_id=application.org_id,
            identity_id=identity_id,
            application_id=application.id,
            scopes=granted,
            auth_method=application.auth_method,
            mcp_access=application.mcp_access,
            api_access=application.api_access,
        )

    def _authenticate_personal_token(self, token: str) -> ResolvedCaller | None:
        personal_token = self._personal_tokens.get_by_token_hash(hash_token(token))
        if personal_token is None:
            return None
        granted = self._permissions.resolve_permissions(personal_token.identity_id, personal_token.org_id)
        self._personal_tokens.touch_last_used(personal_token.id)
        return ResolvedCaller(
            org_id=personal_token.org_id,
            identity_id=personal_token.identity_id,
            application_id=None,
            scopes=granted,
            auth_method="personal_access_token",
            mcp_access=personal_token.mcp_access,
            api_access=True,
        )

    def authenticate_bearer_token(self, token: str) -> ResolvedCaller | None:
        # A JWT is dot-delimited and fails decode fast if it isn't one — a bare personal access
        # token (secrets.token_urlsafe output) never collides with that shape, so trying JWT first
        # is cheap and unambiguous.
        return self._authenticate_jwt(token) or self._authenticate_personal_token(token)
