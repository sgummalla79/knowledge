from app.application.token_service import TokenService
from app.config import config
from app.constants import DEFAULT_MCP_APPLICATION_ID, DEFAULT_MCP_APPLICATION_SCOPES
from app.infrastructure.auth.bootstrap import bootstrap_default_mcp_application
from app.infrastructure.auth.secrets import derive_default_mcp_client_secret, hash_secret
from app.infrastructure.orm import Application as ApplicationModel
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from app.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository


def test_bootstrap_creates_the_default_application(db_session):
    bootstrap_default_mcp_application(db_session)

    application = ApplicationRepository(db_session).get(DEFAULT_MCP_APPLICATION_ID)
    assert application is not None
    assert application.allowed_scopes == DEFAULT_MCP_APPLICATION_SCOPES


def test_bootstrap_is_idempotent(db_session):
    bootstrap_default_mcp_application(db_session)
    bootstrap_default_mcp_application(db_session)  # must not raise or duplicate

    matches = [a for a in ApplicationRepository(db_session).list() if a.id == DEFAULT_MCP_APPLICATION_ID]
    assert len(matches) == 1


def test_bootstrap_stores_the_deterministically_derived_secret(db_session):
    bootstrap_default_mcp_application(db_session)

    model = db_session.query(ApplicationModel).filter(ApplicationModel.id == DEFAULT_MCP_APPLICATION_ID).one()
    expected_secret = derive_default_mcp_client_secret(config.secret_key)
    assert model.client_secret_hash == hash_secret(expected_secret)


def test_default_application_secret_actually_authenticates(app_context, db_session):
    bootstrap_default_mcp_application(db_session)

    applications = ApplicationRepository(db_session)
    token_service = TokenService(
        applications, RefreshTokenRepository(db_session), AuthorizationCodeRepository(db_session)
    )
    raw_secret = derive_default_mcp_client_secret(config.secret_key)

    result = token_service.client_credentials_grant(
        DEFAULT_MCP_APPLICATION_ID, raw_secret, ["libraries:read", "query:execute"]
    )

    assert result["access_token"]
    assert result["scope"] == "libraries:read query:execute"
