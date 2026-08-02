from datetime import datetime, timedelta, timezone

import pytest

from app.application.application_service import ApplicationService
from app.application.token_service import TokenService
from app.domain.errors import InvalidClientError, InvalidGrantError, ValidationError
from app.infrastructure.auth.jwt_tokens import decode_access_token
from app.infrastructure.auth.secrets import hash_secret
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository


def _services(db_session):
    applications = ApplicationRepository(db_session)
    refresh_tokens = RefreshTokenRepository(db_session)
    authorization_codes = AuthorizationCodeRepository(db_session)
    return (
        ApplicationService(applications, refresh_tokens),
        TokenService(applications, refresh_tokens, authorization_codes),
    )


def test_client_credentials_grant_issues_a_working_access_token(app_context, db_session):
    application_service, token_service = _services(db_session)
    raw_secret, application = application_service.register("mcp-server", ["libraries:read", "query:execute"])
    db_session.commit()

    result = token_service.client_credentials_grant(application.id, raw_secret, ["libraries:read", "query:execute"])

    assert result["token_type"] == "Bearer"
    assert "refresh_token" not in result
    claims = decode_access_token(result["access_token"])
    assert claims["sub"] == str(application.id)
    assert claims["scope"] == "libraries:read query:execute"


def test_client_credentials_grant_with_offline_access_issues_refresh_token(app_context, db_session):
    application_service, token_service = _services(db_session)
    raw_secret, application = application_service.register(
        "mcp-server", ["libraries:read", "query:execute", "offline_access"]
    )
    db_session.commit()

    result = token_service.client_credentials_grant(
        application.id, raw_secret, ["libraries:read", "query:execute", "offline_access"]
    )

    assert "refresh_token" in result
    # offline_access is a control flag, not a resource scope — it must never leak into the
    # access token's own scope claim.
    claims = decode_access_token(result["access_token"])
    assert "offline_access" not in claims["scope"].split()
    assert result["scope"] == "libraries:read query:execute"


def test_client_credentials_grant_rejects_scope_outside_allowed(app_context, db_session):
    application_service, token_service = _services(db_session)
    raw_secret, application = application_service.register("mcp-server", ["libraries:read"])
    db_session.commit()

    with pytest.raises(ValidationError) as exc_info:
        token_service.client_credentials_grant(application.id, raw_secret, ["libraries:write"])
    assert exc_info.value.code == "invalid_scope"


def test_client_credentials_grant_wrong_secret_raises_invalid_client(app_context, db_session):
    application_service, token_service = _services(db_session)
    _, application = application_service.register("mcp-server", ["libraries:read"])
    db_session.commit()

    with pytest.raises(InvalidClientError):
        token_service.client_credentials_grant(application.id, "totally-wrong-secret", ["libraries:read"])


def test_refresh_token_grant_reissues_access_token_with_original_scope(app_context, db_session):
    application_service, token_service = _services(db_session)
    raw_secret, application = application_service.register(
        "mcp-server", ["libraries:read", "offline_access"]
    )
    db_session.commit()
    first = token_service.client_credentials_grant(application.id, raw_secret, ["libraries:read", "offline_access"])
    db_session.commit()

    second = token_service.refresh_token_grant(first["refresh_token"])

    assert second["scope"] == "libraries:read"
    claims = decode_access_token(second["access_token"])
    assert claims["scope"] == "libraries:read"


def test_refresh_token_is_reusable_not_rotated(app_context, db_session):
    application_service, token_service = _services(db_session)
    raw_secret, application = application_service.register("mcp-server", ["libraries:read", "offline_access"])
    db_session.commit()
    first = token_service.client_credentials_grant(application.id, raw_secret, ["libraries:read", "offline_access"])
    db_session.commit()

    # Using the same refresh token twice must both succeed — no rotation.
    token_service.refresh_token_grant(first["refresh_token"])
    second_use = token_service.refresh_token_grant(first["refresh_token"])
    assert second_use["access_token"]


def test_refresh_token_grant_invalid_raises(app_context, db_session):
    _, token_service = _services(db_session)
    with pytest.raises(InvalidGrantError):
        token_service.refresh_token_grant("not-a-real-token")


def test_revoked_refresh_token_fails(app_context, db_session):
    application_service, token_service = _services(db_session)
    raw_secret, application = application_service.register("mcp-server", ["libraries:read", "offline_access"])
    db_session.commit()
    result = token_service.client_credentials_grant(application.id, raw_secret, ["libraries:read", "offline_access"])
    db_session.commit()

    application_service.revoke_application_token(application.id)
    db_session.commit()

    with pytest.raises(InvalidGrantError):
        token_service.refresh_token_grant(result["refresh_token"])


def test_expired_refresh_token_fails(app_context, db_session):
    application_service, _ = _services(db_session)
    _, application = application_service.register("mcp-server", ["libraries:read"])
    db_session.commit()

    refresh_tokens = RefreshTokenRepository(db_session)
    raw_token = "manually-issued-expired-token"
    refresh_tokens.create(
        application_id=application.id,
        token_hash=hash_secret(raw_token),
        scope=["libraries:read"],
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.commit()

    _, token_service = _services(db_session)
    with pytest.raises(InvalidGrantError):
        token_service.refresh_token_grant(raw_token)
