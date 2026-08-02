from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import EmbeddingProviderToggle, WebCrawlSettings

# HTTP-layer only — EmbeddingProviderSettingsService/WebCrawlSettingsService are mocked. Real
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


def _toggle(provider, enabled):
    return EmbeddingProviderToggle(id=uuid4(), provider=provider, enabled=enabled, updated_at=datetime.now(timezone.utc))


def _crawl_settings(user_agent="python-requests/2.32.3"):
    return WebCrawlSettings(user_agent=user_agent, updated_at=datetime.now(timezone.utc))


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.get_status", return_value=_crawl_settings())
def test_configuration_renders_provider_status(_get_status, _get_user, client):
    _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderSettingsService.list_providers",
        return_value=[_toggle("ollama", True), _toggle("voyage", False)],
    ):
        response = client.get("/dashboard/configuration")

    assert response.status_code == 200
    assert b"ollama" in response.data
    assert b"voyage" in response.data
    assert b"enabled" in response.data
    assert b"disabled" in response.data


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.EmbeddingProviderSettingsService.list_providers", return_value=[])
def test_configuration_renders_web_crawl_user_agent(_list_providers, _get_user, client):
    _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.WebCrawlSettingsService.get_status",
        return_value=_crawl_settings("custom-agent/1.0"),
    ):
        response = client.get("/dashboard/configuration")

    assert response.status_code == 200
    assert b"custom-agent/1.0" in response.data


def test_update_web_crawl_settings_calls_service(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.update") as update:
        response = client.post(
            "/dashboard/web-crawl-settings",
            data={"csrf_token": csrf, "user_agent": "python-requests/2.32.3"},
        )
    assert response.status_code == 302
    update.assert_called_once_with("python-requests/2.32.3")


def test_update_web_crawl_settings_missing_csrf_does_not_call_service(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.update") as update:
        response = client.post(
            "/dashboard/web-crawl-settings",
            data={"csrf_token": "wrong", "user_agent": "python-requests/2.32.3"},
        )
    assert response.status_code == 302
    update.assert_not_called()


def test_update_web_crawl_settings_blank_value_does_not_call_service(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.update") as update:
        response = client.post(
            "/dashboard/web-crawl-settings",
            data={"csrf_token": csrf, "user_agent": "   "},
        )
    assert response.status_code == 302
    update.assert_not_called()


def test_update_web_crawl_settings_requires_login(client):
    response = client.post("/dashboard/web-crawl-settings", data={"user_agent": "x"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_configuration_requires_login(client):
    response = client.get("/dashboard/configuration")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_toggle_disable_calls_service_with_false(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderSettingsService.set_enabled") as set_enabled:
        response = client.post(
            "/dashboard/embedding-providers/voyage/toggle",
            data={"csrf_token": csrf, "enabled": "false"},
        )
    assert response.status_code == 302
    set_enabled.assert_called_once_with("voyage", False)


def test_toggle_enable_calls_service_with_true(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderSettingsService.set_enabled") as set_enabled:
        response = client.post(
            "/dashboard/embedding-providers/voyage/toggle",
            data={"csrf_token": csrf, "enabled": "true"},
        )
    assert response.status_code == 302
    set_enabled.assert_called_once_with("voyage", True)


def test_toggle_missing_csrf_does_not_call_service(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.EmbeddingProviderSettingsService.set_enabled") as set_enabled:
        response = client.post(
            "/dashboard/embedding-providers/voyage/toggle",
            data={"csrf_token": "wrong", "enabled": "false"},
        )
    assert response.status_code == 302
    set_enabled.assert_not_called()


def test_toggle_requires_login(client):
    response = client.post("/dashboard/embedding-providers/voyage/toggle", data={"enabled": "false"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
