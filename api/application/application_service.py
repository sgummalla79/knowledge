import secrets
from uuid import UUID

from api.constants import APPLICATION_API_KEY_TOKEN_BYTES, APPLICATION_CLIENT_SECRET_BYTES, APPLICATION_SCOPES
from api.domain import error_codes
from api.domain.entities import Application
from api.domain.errors import NotFoundError, ValidationError
from api.domain.ports import (
    ApplicationApiKeyRepositoryPort,
    ApplicationOAuthClientRepositoryPort,
    ApplicationRepositoryPort,
    IdentityRepositoryPort,
    OrgMemberRepositoryPort,
    ProfileRepositoryPort,
)
from api.infrastructure.auth.passwords import hash_password
from api.infrastructure.auth.token_hashing import hash_token


class ApplicationService:
    def __init__(
        self,
        applications: ApplicationRepositoryPort,
        api_keys: ApplicationApiKeyRepositoryPort,
        identities: IdentityRepositoryPort,
        org_members: OrgMemberRepositoryPort,
        profiles: ProfileRepositoryPort,
        oauth_clients: ApplicationOAuthClientRepositoryPort,
    ):
        self._applications = applications
        self._api_keys = api_keys
        self._identities = identities
        self._org_members = org_members
        self._profiles = profiles
        self._oauth_clients = oauth_clients

    def _validate_scopes(self, scopes: list[str]) -> None:
        if not scopes:
            raise ValidationError(error_codes.INVALID_SCOPE, "At least one scope is required.", field="scopes")
        invalid = sorted(set(scopes) - set(APPLICATION_SCOPES))
        if invalid:
            raise ValidationError(
                error_codes.INVALID_SCOPE, f"Unknown scope(s): {', '.join(invalid)}", field="scopes"
            )

    def _issue_api_key(self, application_id: UUID) -> str:
        raw_key = secrets.token_urlsafe(APPLICATION_API_KEY_TOKEN_BYTES)
        self._api_keys.create(application_id, hash_token(raw_key), raw_key[:12])
        return raw_key

    def create(
        self,
        org_id: UUID,
        name: str,
        description: str | None,
        auth_method: str,
        scopes: list[str],
        created_by: UUID,
        mcp_access: bool = False,
        api_access: bool = True,
    ) -> tuple[Application, str]:
        self._validate_scopes(scopes)
        # A service identity that can never log in — satisfies every created_by/owner_id-style FK
        # this schema points at identities.id, since a machine caller has no human behind it. Same
        # unusable-random-password pattern OrgMembershipService.invite_member uses for a
        # not-yet-registered invitee.
        service_identity = self._identities.create(
            f"app-{secrets.token_hex(12)}@applications.internal",
            hash_password(secrets.token_urlsafe(32)),
            name=f"{name} (connected application)",
            must_change_password=False,
        )
        application = self._applications.create(
            org_id,
            name,
            auth_method,
            service_identity.id,
            description=description,
            mcp_access=mcp_access,
            api_access=api_access,
            created_by=created_by,
            last_modified_by=created_by,
        )
        # Assigning the org's Admin profile here is not a privilege escalation: a request from
        # this application is gated by its own application_scopes before any profile-based route
        # logic runs (see AppAuthService/require_permission's api_key branch, which never
        # consults this identity's profile at all) — this membership row exists only so the
        # schema's created_by/owner_id-style FKs resolve, and to preserve this identity's ability
        # to pass permission checks a *human* member with this application's scopes could
        # otherwise not reach (mirrors the "role='admin'" it was assigned before profiles existed).
        admin_profile = self._profiles.get_admin_profile(org_id)
        self._org_members.create(org_id, service_identity.id, admin_profile.id)
        self._applications.set_scopes(application.id, scopes, granted_by=created_by)
        raw_key = self._issue_api_key(application.id)
        return application, raw_key

    def _get_or_404(self, org_id: UUID, application_id: UUID) -> Application:
        application = self._applications.get(application_id)
        if application is None or application.org_id != org_id:
            raise NotFoundError(error_codes.APPLICATION_NOT_FOUND, "Connected application not found.")
        return application

    def get(self, org_id: UUID, application_id: UUID) -> tuple[Application, list[str]]:
        application = self._get_or_404(org_id, application_id)
        return application, self._applications.list_scopes(application.id)

    def list_for_org(self, org_id: UUID) -> list[tuple[Application, list[str]]]:
        applications = self._applications.list_by_org(org_id)
        return [(application, self._applications.list_scopes(application.id)) for application in applications]

    def update(
        self, org_id: UUID, application_id: UUID, name: str, description: str | None, scopes: list[str]
    ) -> tuple[Application, list[str]]:
        existing = self._get_or_404(org_id, application_id)
        application = self._applications.update(application_id, name, description)
        # scopes only apply to api_key — oauth_client_credentials has none of its own (its
        # permissions come from its execute-as identity's profile), so `scopes` is ignored for it
        # rather than requiring the caller to pass a meaningless non-empty list just to rename it.
        if existing.auth_method != "api_key":
            return application, self._applications.list_scopes(application_id)
        self._validate_scopes(scopes)
        self._applications.set_scopes(application_id, scopes, granted_by=None)
        return application, scopes

    def rotate_api_key(self, org_id: UUID, application_id: UUID) -> tuple[Application, str]:
        application = self._get_or_404(org_id, application_id)
        raw_key = secrets.token_urlsafe(APPLICATION_API_KEY_TOKEN_BYTES)
        self._api_keys.rotate(application_id, hash_token(raw_key), raw_key[:12])
        return application, raw_key

    def revoke(self, org_id: UUID, application_id: UUID, revoked_by: UUID) -> tuple[Application, list[str]]:
        self._get_or_404(org_id, application_id)
        application = self._applications.revoke(application_id, revoked_by)
        return application, self._applications.list_scopes(application_id)

    def delete(self, org_id: UUID, application_id: UUID) -> None:
        self._get_or_404(org_id, application_id)
        self._applications.delete(application_id)

    def create_client_credentials(
        self,
        org_id: UUID,
        name: str,
        description: str | None,
        execute_as_identity_id: UUID,
        created_by: UUID,
        mcp_access: bool = False,
        api_access: bool = True,
    ) -> tuple[Application, str]:
        """No synthetic identity, no new org_members row (unlike create()/api_key) — the
        execute-as identity is a real, already-existing member, and PermissionService resolves
        its permissions the same way it does for that member's own session. service_identity_id
        (NOT NULL) is set equal to execute_as_identity_id purely to satisfy that column; nothing
        reads it for this auth method."""
        if self._org_members.get(org_id, execute_as_identity_id) is None:
            raise ValidationError(
                error_codes.INVALID_EXECUTE_AS_IDENTITY,
                "This identity is not a member of this organization.",
                field="execute_as_identity_id",
            )
        application = self._applications.create(
            org_id,
            name,
            "oauth_client_credentials",
            execute_as_identity_id,
            execute_as_identity_id=execute_as_identity_id,
            description=description,
            mcp_access=mcp_access,
            api_access=api_access,
            created_by=created_by,
            last_modified_by=created_by,
        )
        raw_secret = secrets.token_urlsafe(APPLICATION_CLIENT_SECRET_BYTES)
        self._oauth_clients.create(application.id, hash_token(raw_secret))
        return application, raw_secret

    def rotate_client_secret(self, org_id: UUID, application_id: UUID) -> tuple[Application, str]:
        application = self._get_or_404(org_id, application_id)
        raw_secret = secrets.token_urlsafe(APPLICATION_CLIENT_SECRET_BYTES)
        self._oauth_clients.rotate(application_id, hash_token(raw_secret))
        return application, raw_secret

    def create_authorization_code_client(
        self,
        org_id: UUID,
        name: str,
        description: str | None,
        redirect_uris: list[str],
        created_by: UUID,
        mcp_access: bool = False,
        api_access: bool = True,
    ) -> Application:
        """No execute-as identity to pick — whoever completes the consent screen each time is the
        identity a token resolves to (see OAuthAuthorizationService.exchange_authorization_code).
        Unlike api_key's synthetic identity, this one deliberately gets no org_members row: nothing
        ever reads service_identity_id for this auth method (the real actor always comes from
        authorization_codes.identity_id / refresh_tokens.identity_id), so giving it a membership
        would only add a phantom row to the org's member list for no functional benefit. No secret
        is generated — this is a public, PKCE-only client (RFC 8252)."""
        if not redirect_uris:
            raise ValidationError(
                error_codes.INVALID_REDIRECT_URIS, "At least one redirect_uri is required.", field="redirect_uris"
            )
        placeholder_identity = self._identities.create(
            f"app-{secrets.token_hex(12)}@applications.internal",
            hash_password(secrets.token_urlsafe(32)),
            name=f"{name} (connected application)",
            must_change_password=False,
        )
        application = self._applications.create(
            org_id,
            name,
            "oauth_authorization_code",
            placeholder_identity.id,
            description=description,
            mcp_access=mcp_access,
            api_access=api_access,
            created_by=created_by,
            last_modified_by=created_by,
        )
        self._oauth_clients.create(application.id, None, redirect_uris)
        return application
