from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.application.scope_validation import validate_scope_subset
from app.constants import AUTHORIZATION_CODE_TTL_SECONDS
from app.domain import error_codes
from app.domain.entities import Application
from app.domain.errors import InvalidRedirectUriError, UnsupportedResponseTypeError, ValidationError
from app.domain.ports import ApplicationRepositoryPort, AuthorizationCodeRepositoryPort
from app.infrastructure.auth.pkce import SUPPORTED_CODE_CHALLENGE_METHOD
from app.infrastructure.auth.redirect_uri import is_registered_redirect_uri
from app.infrastructure.auth.secrets import generate_secret, hash_secret


class AuthorizeService:
    """Backs GET/POST /oauth/authorize (RFC 6749 §4.1 + PKCE, RFC 7636).

    Split into two validation steps on purpose: `validate_request` covers everything that must be
    checked *before* it's safe to redirect back to the caller at all (unknown client_id, or a
    redirect_uri that isn't registered) — failures here must render an error page, never a
    redirect, per OAuth security guidance. `validate_authorization_params` covers everything that,
    once the redirect_uri is trusted, is safe to report back via `?error=...&state=...`.
    """

    def __init__(self, applications: ApplicationRepositoryPort, codes: AuthorizationCodeRepositoryPort):
        self._applications = applications
        self._codes = codes

    def validate_request(self, client_id: UUID, redirect_uri: str) -> Application:
        application = self._applications.get(client_id)
        if application is None or not is_registered_redirect_uri(redirect_uri, application.redirect_uris):
            raise InvalidRedirectUriError()
        return application

    def validate_authorization_params(
        self, application: Application, response_type: str, scope: list[str], code_challenge_method: str
    ) -> None:
        if response_type != "code":
            raise UnsupportedResponseTypeError()
        if code_challenge_method != SUPPORTED_CODE_CHALLENGE_METHOD:
            raise ValidationError(
                error_codes.INVALID_REQUEST,
                f"code_challenge_method must be {SUPPORTED_CODE_CHALLENGE_METHOD}.",
                field="code_challenge_method",
            )
        validate_scope_subset(scope, application.allowed_scopes)

    def create_authorization_code(
        self,
        application: Application,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: list[str],
    ) -> str:
        raw_code = generate_secret()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTHORIZATION_CODE_TTL_SECONDS)
        self._codes.create(
            application_id=application.id,
            code_hash=hash_secret(raw_code),
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
            expires_at=expires_at,
        )
        return raw_code
