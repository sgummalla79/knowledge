from uuid import UUID

from api.application.permission_service import PermissionService
from api.domain.entities import ResolvedCaller
from api.domain.ports import ApplicationApiKeyRepositoryPort, ApplicationRepositoryPort
from api.infrastructure.auth.jwt_tokens import decode_access_token
from api.infrastructure.auth.token_hashing import hash_token


class AppAuthService:
    """Resolves a machine caller's bearer token to who it is and what it's allowed to do.
    Deliberately framework-free (no Flask imports) so this exact logic is reusable, unmodified, by
    both the Flask require_permission decorator (api/presentation/routes/app_auth.py) and
    api/mcp_server/ — no duplicated auth logic between the two.

    Two independent verification paths coexist deliberately: a client_credentials-issued JWT
    resolves permissions via PermissionService (the execute-as identity's profile — the same
    function every human session request goes through), while an api_key (Phase 1) still checks
    its own application_scopes directly, never touching PermissionService at all — that method
    was intentionally left on its original, separate model."""

    def __init__(
        self,
        applications: ApplicationRepositoryPort,
        api_keys: ApplicationApiKeyRepositoryPort,
        permissions: PermissionService,
    ):
        self._applications = applications
        self._api_keys = api_keys
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
        )

    def _authenticate_api_key(self, token: str) -> ResolvedCaller | None:
        api_key = self._api_keys.get_by_key_hash(hash_token(token))
        if api_key is None or api_key.revoked_at is not None:
            return None
        application = self._applications.get(api_key.application_id)
        if application is None or application.status != "active":
            return None
        scopes = frozenset(self._applications.list_scopes(application.id))
        self._api_keys.touch_last_used(application.id)
        return ResolvedCaller(
            org_id=application.org_id,
            identity_id=application.service_identity_id,
            application_id=application.id,
            scopes=scopes,
            auth_method=application.auth_method,
            mcp_access=application.mcp_access,
        )

    def authenticate_bearer_token(self, token: str) -> ResolvedCaller | None:
        # A JWT is dot-delimited and fails decode fast if it isn't one — a bare api_key
        # (secrets.token_urlsafe output) never collides with that shape, so trying JWT first is
        # cheap and unambiguous.
        return self._authenticate_jwt(token) or self._authenticate_api_key(token)
