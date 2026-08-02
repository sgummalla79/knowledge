from datetime import datetime, timedelta, timezone

import pytest

from app.application.application_service import ApplicationService
from app.application.authorize_service import AuthorizeService
from app.application.client_registration_service import ClientRegistrationService
from app.application.token_service import TokenService
from app.domain.errors import (
    InvalidClientError,
    InvalidGrantError,
    InvalidRedirectUriError,
    UnsupportedResponseTypeError,
    ValidationError,
)
from app.infrastructure.auth.jwt_tokens import decode_access_token
from app.infrastructure.auth.pkce import compute_code_challenge
from app.infrastructure.auth.secrets import generate_secret, hash_secret
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository

_REDIRECT_URI = "http://127.0.0.1:51000/callback"
_CODE_VERIFIER = "test-code-verifier-value-1234567890"


def _services(db_session):
    applications = ApplicationRepository(db_session)
    refresh_tokens = RefreshTokenRepository(db_session)
    authorization_codes = AuthorizationCodeRepository(db_session)
    return (
        ApplicationService(applications, refresh_tokens),
        AuthorizeService(applications, authorization_codes),
        TokenService(applications, refresh_tokens, authorization_codes),
    )


def _register_client(application_service, db_session, scopes=None):
    scopes = scopes or ["libraries:read", "query:execute", "offline_access"]
    raw_secret, application = application_service.register("claude-code", scopes, [_REDIRECT_URI])
    db_session.commit()
    return raw_secret, application


def test_authorization_code_grant_happy_path(app_context, db_session):
    application_service, authorize_service, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)

    challenge = compute_code_challenge(_CODE_VERIFIER)
    code = authorize_service.create_authorization_code(
        application, _REDIRECT_URI, challenge, "S256", ["libraries:read", "offline_access"]
    )
    db_session.commit()

    result = token_service.authorization_code_grant(code, _REDIRECT_URI, application.id, raw_secret, _CODE_VERIFIER)

    assert result["token_type"] == "Bearer"
    assert "refresh_token" in result
    claims = decode_access_token(result["access_token"])
    assert claims["sub"] == str(application.id)
    assert claims["scope"] == "libraries:read"


def test_authorization_code_is_single_use(app_context, db_session):
    application_service, authorize_service, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)
    challenge = compute_code_challenge(_CODE_VERIFIER)
    code = authorize_service.create_authorization_code(
        application, _REDIRECT_URI, challenge, "S256", ["libraries:read"]
    )
    db_session.commit()

    token_service.authorization_code_grant(code, _REDIRECT_URI, application.id, raw_secret, _CODE_VERIFIER)
    db_session.commit()

    with pytest.raises(InvalidGrantError):
        token_service.authorization_code_grant(code, _REDIRECT_URI, application.id, raw_secret, _CODE_VERIFIER)


def test_authorization_code_expired_rejected(app_context, db_session):
    application_service, _, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)
    authorization_codes = AuthorizationCodeRepository(db_session)
    challenge = compute_code_challenge(_CODE_VERIFIER)

    raw_code = generate_secret()
    authorization_codes.create(
        application_id=application.id,
        code_hash=hash_secret(raw_code),
        redirect_uri=_REDIRECT_URI,
        code_challenge=challenge,
        code_challenge_method="S256",
        scope=["libraries:read"],
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db_session.commit()

    with pytest.raises(InvalidGrantError):
        token_service.authorization_code_grant(raw_code, _REDIRECT_URI, application.id, raw_secret, _CODE_VERIFIER)


def test_authorization_code_wrong_pkce_verifier_rejected(app_context, db_session):
    application_service, authorize_service, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)
    challenge = compute_code_challenge(_CODE_VERIFIER)
    code = authorize_service.create_authorization_code(
        application, _REDIRECT_URI, challenge, "S256", ["libraries:read"]
    )
    db_session.commit()

    with pytest.raises(InvalidGrantError):
        token_service.authorization_code_grant(code, _REDIRECT_URI, application.id, raw_secret, "wrong-verifier")


def test_authorization_code_redirect_uri_mismatch_rejected(app_context, db_session):
    application_service, authorize_service, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)
    challenge = compute_code_challenge(_CODE_VERIFIER)
    code = authorize_service.create_authorization_code(
        application, _REDIRECT_URI, challenge, "S256", ["libraries:read"]
    )
    db_session.commit()

    with pytest.raises(InvalidGrantError):
        token_service.authorization_code_grant(
            code, "http://127.0.0.1:9999/other-path", application.id, raw_secret, _CODE_VERIFIER
        )


def test_authorization_code_loopback_port_change_still_accepted(app_context, db_session):
    # The redirect_uri sent at token-exchange is allowed to differ only in port from the one used
    # at /oauth/authorize, for loopback hosts (RFC 8252 §7.3) — a CLI client's callback listener
    # commonly binds a fresh ephemeral port each run.
    application_service, authorize_service, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)
    challenge = compute_code_challenge(_CODE_VERIFIER)
    code = authorize_service.create_authorization_code(
        application, _REDIRECT_URI, challenge, "S256", ["libraries:read"]
    )
    db_session.commit()

    result = token_service.authorization_code_grant(
        code, "http://127.0.0.1:9999/callback", application.id, raw_secret, _CODE_VERIFIER
    )
    assert result["access_token"]


def test_authorization_code_wrong_client_secret_rejected(app_context, db_session):
    application_service, authorize_service, token_service = _services(db_session)
    raw_secret, application = _register_client(application_service, db_session)
    challenge = compute_code_challenge(_CODE_VERIFIER)
    code = authorize_service.create_authorization_code(
        application, _REDIRECT_URI, challenge, "S256", ["libraries:read"]
    )
    db_session.commit()

    with pytest.raises(InvalidClientError):
        token_service.authorization_code_grant(code, _REDIRECT_URI, application.id, "wrong-secret", _CODE_VERIFIER)


def test_authorize_validate_request_rejects_unregistered_redirect_uri(app_context, db_session):
    application_service, authorize_service, _ = _services(db_session)
    _, application = _register_client(application_service, db_session)

    with pytest.raises(InvalidRedirectUriError):
        authorize_service.validate_request(application.id, "http://evil.example.com/cb")


def test_authorize_validate_authorization_params_rejects_bad_response_type(app_context, db_session):
    application_service, authorize_service, _ = _services(db_session)
    _, application = _register_client(application_service, db_session)

    with pytest.raises(UnsupportedResponseTypeError):
        authorize_service.validate_authorization_params(application, "token", ["libraries:read"], "S256")


def test_authorize_validate_authorization_params_rejects_scope_outside_allowed(app_context, db_session):
    application_service, authorize_service, _ = _services(db_session)
    _, application = _register_client(application_service, db_session, scopes=["libraries:read"])

    with pytest.raises(ValidationError):
        authorize_service.validate_authorization_params(application, "code", ["libraries:write"], "S256")


def test_dynamic_client_registration_creates_confidential_client(app_context, db_session):
    registration_service = ClientRegistrationService(ApplicationRepository(db_session))

    raw_secret, application = registration_service.register_client("claude-code", [_REDIRECT_URI])
    db_session.commit()

    assert raw_secret
    assert application.redirect_uris == [_REDIRECT_URI]
    assert "libraries:read" in application.allowed_scopes
    assert "libraries:write" not in application.allowed_scopes


def test_dynamic_client_registration_requires_redirect_uris(app_context, db_session):
    registration_service = ClientRegistrationService(ApplicationRepository(db_session))

    with pytest.raises(ValidationError):
        registration_service.register_client("claude-code", [])


def test_dynamic_client_registration_deduplicates_client_name(app_context, db_session):
    registration_service = ClientRegistrationService(ApplicationRepository(db_session))

    _, first = registration_service.register_client("claude-code", [_REDIRECT_URI])
    db_session.commit()
    _, second = registration_service.register_client("claude-code", [_REDIRECT_URI])
    db_session.commit()

    assert first.name != second.name
