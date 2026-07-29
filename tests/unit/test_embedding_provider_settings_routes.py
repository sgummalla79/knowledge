from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from uuid import uuid4

from app import create_app
from app.domain.entities import EmbeddingProviderToggle
from app.domain.errors import ValidationError

# HTTP-layer wiring only — EmbeddingProviderSettingsService is mocked.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _toggle(provider, enabled=True):
    return EmbeddingProviderToggle(
        id=uuid4(), provider=provider, enabled=enabled, updated_at=datetime.now(timezone.utc)
    )


def test_list_returns_all_provider_toggles(client, auth_headers):
    toggles = [_toggle("ollama"), _toggle("voyage", enabled=False), _toggle("openai_compatible")]
    with patch(
        "app.presentation.routes.embedding_provider_settings.EmbeddingProviderSettingsService.list_providers",
        return_value=toggles,
    ):
        response = client.get("/embedding-provider-settings", headers=auth_headers("embedding_settings:read"))

    assert response.status_code == 200
    body = response.get_json()
    assert {item["provider"]: item["enabled"] for item in body} == {
        "ollama": True,
        "voyage": False,
        "openai_compatible": True,
    }


def test_disable_provider_returns_updated_toggle(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_provider_settings.EmbeddingProviderSettingsService.set_enabled",
        return_value=_toggle("voyage", enabled=False),
    ) as mock_set_enabled:
        response = client.put(
            "/embedding-provider-settings/voyage",
            json={"enabled": False},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["provider"] == "voyage"
    assert body["enabled"] is False
    mock_set_enabled.assert_called_once_with("voyage", False)


def test_enable_unknown_provider_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_provider_settings.EmbeddingProviderSettingsService.set_enabled",
        side_effect=ValidationError("unsupported_embedding_provider", "bad provider", field="provider"),
    ):
        response = client.put(
            "/embedding-provider-settings/made-up-provider",
            json={"enabled": True},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "unsupported_embedding_provider"


def test_missing_enabled_field_rejected_by_schema(client, auth_headers):
    response = client.put(
        "/embedding-provider-settings/voyage",
        json={},
        headers=auth_headers("embedding_settings:write"),
    )

    assert response.status_code == 400


def test_missing_auth_returns_401(client):
    response = client.get("/embedding-provider-settings")
    assert response.status_code == 401


def test_missing_write_scope_returns_403(client, auth_headers):
    response = client.put(
        "/embedding-provider-settings/voyage",
        json={"enabled": False},
        headers=auth_headers("embedding_settings:read"),
    )
    assert response.status_code == 403
