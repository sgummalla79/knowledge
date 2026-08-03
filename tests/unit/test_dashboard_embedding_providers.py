from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.application.embedding_provider_settings_service import EmbeddingProviderConfigStatus
from app.domain.entities import WebCrawlSettings
from app.domain.errors import ValidationError

# HTTP-layer only — EmbeddingProviderConfigService/WebCrawlSettingsService are mocked. Real
# enable/disable and settings-update behavior are covered by their own service-level tests.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def _status(provider="voyage", enabled=False, configured=False, locked=False, chunk_count=0):
    return EmbeddingProviderConfigStatus(
        provider=provider,
        enabled=enabled,
        configured=configured,
        locked=locked,
        chunk_count=chunk_count,
        model="voyage-3" if configured else None,
        base_url=None,
        dimensions=1024 if configured else None,
        chunk_size=800,
        chunk_overlap=100,
        updated_at=datetime.now(timezone.utc) if configured else None,
    )


def _crawl_settings(user_agent="python-requests/2.32.3"):
    return WebCrawlSettings(user_agent=user_agent, updated_at=datetime.now(timezone.utc))


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.get_status", return_value=_crawl_settings())
def test_configuration_renders_web_crawl_user_agent(_get_status, _get_user, client):
    _logged_in(client)
    response = client.get("/dashboard/configuration")

    assert response.status_code == 200
    assert b"python-requests/2.32.3" in response.data


def test_configuration_requires_login(client):
    response = client.get("/dashboard/configuration")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
def test_embedding_provider_page_renders_status(_get_user, client):
    _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderConfigService.get_status",
        return_value=_status("voyage", enabled=True, configured=True),
    ):
        response = client.get("/dashboard/configuration/embeddings/voyage")

    assert response.status_code == 200
    assert b"Voyage" in response.data
    assert b"enabled" in response.data


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
def test_embedding_provider_page_unknown_provider_404s(_get_user, client):
    _logged_in(client)
    response = client.get("/dashboard/configuration/embeddings/not-a-provider")
    assert response.status_code == 404


def test_embedding_provider_page_requires_login(client):
    response = client.get("/dashboard/configuration/embeddings/voyage")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_update_embedding_provider_settings_calls_service(client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderConfigService.update_config",
        return_value=_status("voyage", configured=True),
    ) as update_config:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage",
            data={
                "csrf_token": csrf,
                "api_key": "voy-secret",
                "model": "voyage-3",
                "dimensions": "1024",
                "chunk_size": "800",
                "chunk_overlap": "100",
            },
        )
    assert response.status_code == 302
    update_config.assert_called_once_with("voyage", "voyage-3", "voy-secret", None, 1024, 800, 100)


def test_update_embedding_provider_settings_blank_api_key_keeps_current_key(client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderSettingsRepository.get",
        return_value=_fake_config_with_key("voyage", "existing-key"),
    ), patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderConfigService.update_config",
        return_value=_status("voyage", configured=True),
    ) as update_config:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage",
            data={
                "csrf_token": csrf,
                "api_key": "",
                "model": "voyage-3",
                "dimensions": "1024",
                "chunk_size": "800",
                "chunk_overlap": "100",
            },
        )
    assert response.status_code == 302
    update_config.assert_called_once_with("voyage", "voyage-3", "existing-key", None, 1024, 800, 100)


def _fake_config_with_key(provider, api_key):
    from app.domain.entities import EmbeddingProviderConfig

    return EmbeddingProviderConfig(
        id=uuid4(),
        provider=provider,
        enabled=False,
        model="voyage-3",
        api_key=api_key,
        base_url=None,
        dimensions=1024,
        chunk_size=800,
        chunk_overlap=100,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.EmbeddingProviderConfigService.get_status", return_value=_status("voyage"))
def test_update_embedding_provider_settings_missing_csrf_does_not_call_service(_get_status, _get_user, client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderConfigService.update_config") as update_config:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage",
            data={"csrf_token": "wrong", "api_key": "voy-secret", "model": "voyage-3", "dimensions": "1024", "chunk_size": "800", "chunk_overlap": "100"},
        )
    assert response.status_code == 400
    update_config.assert_not_called()


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.EmbeddingProviderConfigService.get_status", return_value=_status("voyage"))
def test_update_embedding_provider_settings_non_numeric_dimensions_does_not_call_service(_get_status, _get_user, client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderConfigService.update_config") as update_config:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage",
            data={"csrf_token": csrf, "api_key": "voy-secret", "model": "voyage-3", "dimensions": "not-a-number", "chunk_size": "800", "chunk_overlap": "100"},
        )
    assert response.status_code == 200
    update_config.assert_not_called()


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.EmbeddingProviderConfigService.get_status", return_value=_status("voyage"))
def test_update_embedding_provider_settings_validation_error_renders_message(_get_status, _get_user, client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderConfigService.update_config",
        side_effect=ValidationError("embedding_dimension_mismatch", "boom", field="dimensions"),
    ):
        response = client.post(
            "/dashboard/configuration/embeddings/voyage",
            data={"csrf_token": csrf, "api_key": "voy-secret", "model": "voyage-3", "dimensions": "1024", "chunk_size": "800", "chunk_overlap": "100"},
        )
    assert response.status_code == 200
    assert b"boom" in response.data


def test_update_embedding_provider_settings_requires_login(client):
    response = client.post("/dashboard/configuration/embeddings/voyage", data={"model": "voyage-3"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_enable_embedding_provider_calls_service(client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderConfigService.enable",
        return_value=_status("voyage", enabled=True, configured=True),
    ) as enable:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage/enable", data={"csrf_token": csrf}
        )
    assert response.status_code == 302
    enable.assert_called_once_with("voyage")


def test_enable_embedding_provider_missing_csrf_does_not_call_service(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderConfigService.enable") as enable:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage/enable", data={"csrf_token": "wrong"}
        )
    assert response.status_code == 302
    enable.assert_not_called()


def test_disable_embedding_provider_calls_service(client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderConfigService.disable",
        return_value=_status("voyage", configured=True),
    ) as disable:
        response = client.post(
            "/dashboard/configuration/embeddings/voyage/disable", data={"csrf_token": csrf}
        )
    assert response.status_code == 302
    disable.assert_called_once_with("voyage")


def test_disable_embedding_provider_requires_login(client):
    response = client.post("/dashboard/configuration/embeddings/voyage/disable", data={})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
