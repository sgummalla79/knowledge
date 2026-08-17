from uuid import uuid4

import pytest

from app.application.application_service import ApplicationService
from app.application.auth_service import AuthService
from app.domain.errors import AuthenticationError, InvalidGrantError, NotFoundError, ValidationError
from app.infrastructure.auth.bootstrap import bootstrap_default_admin
from app.infrastructure.auth.passwords import verify_password
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository


def test_bootstrap_creates_exactly_one_user_and_is_idempotent(db_session):
    bootstrap_default_admin(db_session)
    bootstrap_default_admin(db_session)  # calling twice must not duplicate

    user = UserRepository(db_session).get()
    assert user is not None
    assert user.email == "admin"
    assert user.must_change_password is True


def test_login_with_correct_and_incorrect_password(db_session):
    bootstrap_default_admin(db_session)
    db_session.commit()
    service = AuthService(UserRepository(db_session))

    user = service.login("admin", "admin")
    assert user.email == "admin"

    with pytest.raises(AuthenticationError):
        service.login("admin", "wrong-password")


def test_change_password_clears_must_change_flag(db_session):
    bootstrap_default_admin(db_session)
    db_session.commit()
    user_repo = UserRepository(db_session)
    service = AuthService(user_repo)
    user = service.login("admin", "admin")

    service.change_password(user.id, "a-new-strong-password")
    db_session.commit()

    updated = user_repo.get()
    assert updated.must_change_password is False
    assert verify_password("a-new-strong-password", updated.password_hash)


def _application_service(db_session):
    return ApplicationService(ApplicationRepository(db_session), RefreshTokenRepository(db_session))


def test_register_creates_application_with_working_secret(db_session):
    service = _application_service(db_session)
    raw_secret, application = service.register("mcp-server", ["libraries:read", "query:execute"])
    db_session.commit()

    assert application.name == "mcp-server"
    assert application.allowed_scopes == ["libraries:read", "query:execute"]
    assert len(raw_secret) > 20


def test_register_rejects_duplicate_name(db_session):
    service = _application_service(db_session)
    service.register("mcp-server", ["libraries:read"])
    db_session.commit()

    with pytest.raises(ValidationError) as exc_info:
        service.register("mcp-server", ["query:execute"])
    assert exc_info.value.code == "application_name_taken"


def test_register_rejects_unsupported_scope(db_session):
    service = _application_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.register("mcp-server", ["not:a:real:scope"])
    assert exc_info.value.code == "invalid_scope"


def test_regenerate_secret_invalidates_the_old_one(db_session):
    from app.infrastructure.auth.secrets import hash_secret

    service = _application_service(db_session)
    raw_secret, application = service.register("mcp-server", ["libraries:read"])
    db_session.commit()

    new_secret = service.regenerate_secret(application.id)
    db_session.commit()

    application_repo = ApplicationRepository(db_session)
    assert application_repo.find_by_credentials(application.id, hash_secret(raw_secret)) is None
    assert application_repo.find_by_credentials(application.id, hash_secret(new_secret)) is not None


def test_regenerate_secret_missing_application_raises_not_found(db_session):
    from uuid import uuid4

    service = _application_service(db_session)
    with pytest.raises(NotFoundError):
        service.regenerate_secret(uuid4())


def test_revoke_application_token_revokes_current_token(app_context, db_session):
    from app.application.token_service import TokenService

    service = _application_service(db_session)
    raw_secret, application = service.register("mcp-server", ["libraries:read", "offline_access"])
    db_session.commit()

    token_service = TokenService(
        ApplicationRepository(db_session), RefreshTokenRepository(db_session), AuthorizationCodeRepository(db_session)
    )
    result = token_service.client_credentials_grant(application.id, raw_secret, ["libraries:read", "offline_access"])
    db_session.commit()
    assert "refresh_token" in result

    service.revoke_application_token(application.id)
    db_session.commit()

    with pytest.raises(InvalidGrantError):
        token_service.refresh_token_grant(result["refresh_token"])


def test_delete_application_removes_it_and_cascades_its_refresh_token(app_context, db_session):
    from app.application.token_service import TokenService

    application_repo = ApplicationRepository(db_session)
    refresh_token_repo = RefreshTokenRepository(db_session)
    service = _application_service(db_session)
    raw_secret, application = service.register("mcp-server", ["libraries:read", "offline_access"])
    db_session.commit()

    token_service = TokenService(application_repo, refresh_token_repo, AuthorizationCodeRepository(db_session))
    result = token_service.client_credentials_grant(application.id, raw_secret, ["libraries:read", "offline_access"])
    db_session.commit()

    service.delete_application(application.id)
    db_session.commit()

    assert application_repo.get(application.id) is None
    # The FK's ondelete="CASCADE" should have removed the refresh token too, not just orphaned it.
    with pytest.raises(InvalidGrantError):
        token_service.refresh_token_grant(result["refresh_token"])


def test_delete_application_missing_raises_not_found(db_session):
    service = _application_service(db_session)
    with pytest.raises(NotFoundError):
        service.delete_application(uuid4())
