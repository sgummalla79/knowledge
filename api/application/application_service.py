import secrets
from uuid import UUID

from api.constants import APPLICATION_CLIENT_SECRET_BYTES
from api.domain import error_codes
from api.domain.entities import Application
from api.domain.errors import NotFoundError, ValidationError
from api.domain.ports import (
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
        identities: IdentityRepositoryPort,
        org_members: OrgMemberRepositoryPort,
        profiles: ProfileRepositoryPort,
        oauth_clients: ApplicationOAuthClientRepositoryPort,
    ):
        self._applications = applications
        self._identities = identities
        self._org_members = org_members
        self._profiles = profiles
        self._oauth_clients = oauth_clients

    def _get_or_404(self, org_id: UUID, application_id: UUID) -> Application:
        application = self._applications.get(application_id)
        if application is None or application.org_id != org_id:
            raise NotFoundError(error_codes.APPLICATION_NOT_FOUND, "Connected application not found.")
        return application

    def get(self, org_id: UUID, application_id: UUID) -> Application:
        return self._get_or_404(org_id, application_id)

    def list_for_org(self, org_id: UUID) -> list[Application]:
        return self._applications.list_by_org(org_id)

    def update(self, org_id: UUID, application_id: UUID, name: str, description: str | None) -> Application:
        self._get_or_404(org_id, application_id)
        return self._applications.update(application_id, name, description)

    def revoke(self, org_id: UUID, application_id: UUID, revoked_by: UUID) -> Application:
        self._get_or_404(org_id, application_id)
        return self._applications.revoke(application_id, revoked_by)

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
        """No synthetic identity, no new org_members row — the execute-as identity is a real,
        already-existing member, and PermissionService resolves its permissions the same way it
        does for that member's own session. service_identity_id (NOT NULL) is set equal to
        execute_as_identity_id purely to satisfy that column; nothing reads it for this auth
        method."""
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
        This placeholder identity deliberately gets no org_members row: nothing ever reads
        service_identity_id for this auth method (the real actor always comes from
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
