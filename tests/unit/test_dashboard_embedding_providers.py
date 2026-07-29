from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import EmbeddingProviderToggle

# HTTP-layer only — EmbeddingProviderSettingsService is mocked. Real enable/disable behavior is
# covered by tests/unit/test_embedding_provider_settings_service.py.


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


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
def test_configuration_renders_provider_status(_get_user, client):
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


def test_configuration_requires_login(client):
    response = client.get("/dashboard/configuration")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


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
