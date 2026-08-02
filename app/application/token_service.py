from uuid import UUID

from app.application.scope_validation import validate_scope_subset
from app.constants import ACCESS_TOKEN_TTL_SECONDS, SCOPE_OFFLINE_ACCESS
from app.domain.errors import InvalidClientError, InvalidGrantError
from app.domain.ports import ApplicationRepositoryPort, AuthorizationCodeRepositoryPort, RefreshTokenRepositoryPort
from app.infrastructure.auth.jwt_tokens import issue_access_token
from app.infrastructure.auth.pkce import verify_pkce
from app.infrastructure.auth.redirect_uri import redirect_uri_matches
from app.infrastructure.auth.secrets import generate_secret, hash_secret


class TokenService:
    """Backs POST /oauth/token — the one and only place access/refresh tokens are minted."""

    def __init__(
        self,
        applications: ApplicationRepositoryPort,
        refresh_tokens: RefreshTokenRepositoryPort,
        authorization_codes: AuthorizationCodeRepositoryPort,
    ):
        self._applications = applications
        self._refresh_tokens = refresh_tokens
        self._authorization_codes = authorization_codes

    def client_credentials_grant(self, client_id, client_secret: str, requested_scope: list[str]) -> dict:
        application = self._applications.find_by_credentials(client_id, hash_secret(client_secret))
        if application is None:
            raise InvalidClientError()

        validate_scope_subset(requested_scope, application.allowed_scopes)

        # offline_access is a control flag ("should a refresh token also be issued"), not a
        # resource permission — it never belongs in the access token's own scope claim.
        resource_scopes = [scope for scope in requested_scope if scope != SCOPE_OFFLINE_ACCESS]
        access_token = issue_access_token(str(application.id), resource_scopes, ACCESS_TOKEN_TTL_SECONDS)

        result = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "scope": " ".join(resource_scopes),
        }

        if SCOPE_OFFLINE_ACCESS in requested_scope:
            raw_refresh_token = generate_secret()
            self._refresh_tokens.create(
                application_id=application.id,
                token_hash=hash_secret(raw_refresh_token),
                scope=resource_scopes,
                expires_at=None,
            )
            result["refresh_token"] = raw_refresh_token

        return result

    def refresh_token_grant(self, raw_refresh_token: str) -> dict:
        token = self._refresh_tokens.find_valid_by_hash(hash_secret(raw_refresh_token))
        if token is None:
            raise InvalidGrantError()

        self._refresh_tokens.touch_last_used(token.id)
        access_token = issue_access_token(str(token.application_id), token.scope, ACCESS_TOKEN_TTL_SECONDS)

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "scope": " ".join(token.scope),
        }

    def authorization_code_grant(
        self,
        raw_code: str,
        redirect_uri: str,
        client_id: UUID,
        client_secret: str,
        code_verifier: str,
    ) -> dict:
        application = self._applications.find_by_credentials(client_id, hash_secret(client_secret))
        if application is None:
            raise InvalidClientError()

        code = self._authorization_codes.find_valid_by_hash(hash_secret(raw_code))
        if code is None or code.application_id != application.id:
            raise InvalidGrantError("Invalid, expired, or already-used authorization code.")

        # Single-use regardless of what the checks below find — an authorization code must never
        # be exchangeable twice, even after a failed redirect_uri/PKCE check (RFC 6749 §4.1.2).
        self._authorization_codes.mark_used(code.id)

        if not redirect_uri_matches(redirect_uri, code.redirect_uri):
            raise InvalidGrantError("redirect_uri does not match the original authorization request.")
        if not verify_pkce(code_verifier, code.code_challenge, code.code_challenge_method):
            raise InvalidGrantError("PKCE verification failed.")

        resource_scopes = [scope for scope in code.scope if scope != SCOPE_OFFLINE_ACCESS]
        access_token = issue_access_token(str(application.id), resource_scopes, ACCESS_TOKEN_TTL_SECONDS)

        result = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
            "scope": " ".join(resource_scopes),
        }

        if SCOPE_OFFLINE_ACCESS in code.scope:
            raw_refresh_token = generate_secret()
            self._refresh_tokens.create(
                application_id=application.id,
                token_hash=hash_secret(raw_refresh_token),
                scope=resource_scopes,
                expires_at=None,
            )
            result["refresh_token"] = raw_refresh_token

        return result
