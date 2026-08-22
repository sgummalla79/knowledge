import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from api.constants import (
    ACCESS_TOKEN_TTL_MINUTES,
    AUTHORIZATION_CODE_BYTES,
    AUTHORIZATION_CODE_TTL_SECONDS,
    REFRESH_TOKEN_BYTES,
    REFRESH_TOKEN_TTL_DAYS,
)
from api.domain import error_codes
from api.domain.entities import Application, ApplicationOAuthClient
from api.domain.errors import AuthenticationError, ValidationError
from api.domain.ports import (
    ApplicationOAuthClientRepositoryPort,
    ApplicationRepositoryPort,
    AuthorizationCodeRepositoryPort,
    RefreshTokenRepositoryPort,
)
from api.infrastructure.auth.jwt_tokens import encode_access_token
from api.infrastructure.auth.pkce import verify_code_challenge
from api.infrastructure.auth.redirect_uri import redirect_uri_matches
from api.infrastructure.auth.token_hashing import hash_token

# oauth.py's route layer catches AuthenticationError/ValidationError generically and always
# responds with RFC 6749's {"error": "invalid_client"/"invalid_grant", "error_description": ...}
# shape — this app's usual {code, message, field} envelope doesn't apply to this one endpoint (see
# the module docstring in api/presentation/routes/oauth.py), so the messages here are just for
# logs/debugging, not client-facing codes.
_INVALID_CLIENT_MESSAGE = "Invalid client_id or client_secret."
_INVALID_GRANT_MESSAGE = "Invalid, expired, or already-used grant."


class OAuthAuthorizationService:
    def __init__(
        self,
        applications: ApplicationRepositoryPort,
        oauth_clients: ApplicationOAuthClientRepositoryPort,
        authorization_codes: AuthorizationCodeRepositoryPort,
        refresh_tokens: RefreshTokenRepositoryPort,
    ):
        self._applications = applications
        self._oauth_clients = oauth_clients
        self._authorization_codes = authorization_codes
        self._refresh_tokens = refresh_tokens

    def _issue_access_token(self, application_id: UUID, org_id: UUID, identity_id: UUID) -> str:
        claims = {"sub": str(application_id), "org_id": str(org_id), "identity_id": str(identity_id)}
        return encode_access_token(claims, ACCESS_TOKEN_TTL_MINUTES)

    def issue_client_credentials_token(self, client_id: UUID, client_secret: str) -> str:
        application = self._applications.get(client_id)
        if (
            application is None
            or application.status != "active"
            or application.auth_method != "oauth_client_credentials"
        ):
            # Same error for "no such client" as for "wrong secret" below — this endpoint never
            # distinguishes the two, so it can't be used to enumerate valid client ids.
            raise AuthenticationError(_INVALID_CLIENT_MESSAGE)

        oauth_client = self._oauth_clients.get_by_application(application.id)
        if (
            oauth_client is None
            or oauth_client.revoked_at is not None
            or oauth_client.client_secret_hash != hash_token(client_secret)
        ):
            raise AuthenticationError(_INVALID_CLIENT_MESSAGE)

        return self._issue_access_token(application.id, application.org_id, application.execute_as_identity_id)

    # ── authorization_code + PKCE ──────────────────────────────────────────────────────────────

    def get_authorization_code_client(self, client_id: UUID) -> tuple[Application, ApplicationOAuthClient]:
        """Used by GET/POST /oauth/authorize before anything else — raises AuthenticationError for
        any problem with the client itself, which the route renders as an error PAGE, never a
        redirect (redirect_uri isn't trusted yet at this point)."""
        application = self._applications.get(client_id)
        if (
            application is None
            or application.status != "active"
            or application.auth_method != "oauth_authorization_code"
        ):
            raise AuthenticationError(_INVALID_CLIENT_MESSAGE)
        oauth_client = self._oauth_clients.get_by_application(application.id)
        if oauth_client is None:
            raise AuthenticationError(_INVALID_CLIENT_MESSAGE)
        return application, oauth_client

    def validate_redirect_uri(self, oauth_client: ApplicationOAuthClient, redirect_uri: str) -> None:
        if not any(redirect_uri_matches(registered, redirect_uri) for registered in oauth_client.redirect_uris):
            raise AuthenticationError(_INVALID_CLIENT_MESSAGE)

    def create_authorization_code(
        self, application_id: UUID, org_id: UUID, identity_id: UUID, redirect_uri: str, code_challenge: str, scope: str
    ) -> str:
        raw_code = secrets.token_urlsafe(AUTHORIZATION_CODE_BYTES)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTHORIZATION_CODE_TTL_SECONDS)
        self._authorization_codes.create(
            application_id,
            org_id,
            identity_id,
            code_hash=hash_token(raw_code),
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            scope=scope,
            expires_at=expires_at,
        )
        return raw_code

    def exchange_authorization_code(
        self, code: str, redirect_uri: str, client_id: UUID, code_verifier: str
    ) -> tuple[str, str | None]:
        record = self._authorization_codes.get_by_code_hash(hash_token(code))
        now = datetime.now(timezone.utc)
        if record is None or record.application_id != client_id:
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)
        if record.consumed_at is not None or record.expires_at < now:
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)
        # Exact match against what was actually used at the /authorize step (RFC 6749 §4.1.3) —
        # deliberately not the loopback-fuzzy redirect_uri_matches used against the *registered*
        # list at authorize time; this check exists to prevent code-injection across redirect_uris.
        if record.redirect_uri != redirect_uri:
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)
        if not verify_code_challenge(code_verifier, record.code_challenge):
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)

        application = self._applications.get(record.application_id)
        if application is None or application.status != "active":
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)

        self._authorization_codes.mark_consumed(record.id)
        access_token = self._issue_access_token(application.id, record.org_id, record.identity_id)

        refresh_token = None
        if "offline_access" in record.scope.split():
            raw_refresh = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
            expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
            self._refresh_tokens.create(application.id, record.org_id, record.identity_id, hash_token(raw_refresh), expires_at)
            refresh_token = raw_refresh

        return access_token, refresh_token

    def refresh_access_token(self, refresh_token: str, client_id: UUID) -> str:
        record = self._refresh_tokens.get_by_token_hash(hash_token(refresh_token))
        now = datetime.now(timezone.utc)
        if record is None or record.application_id != client_id:
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)
        if record.revoked_at is not None or record.expires_at < now:
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)

        application = self._applications.get(record.application_id)
        if application is None or application.status != "active":
            raise ValidationError(error_codes.VALIDATION_ERROR, _INVALID_GRANT_MESSAGE)

        self._refresh_tokens.touch_last_used(record.id)
        # Permissions are always re-resolved fresh from the identity's current profile at request
        # time (AppAuthService), never carried over from the original code exchange — refreshing
        # just extends the session, it doesn't snapshot anything.
        return self._issue_access_token(application.id, record.org_id, record.identity_id)
