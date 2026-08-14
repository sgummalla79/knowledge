from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from app.domain.entities import RouterSettings

# HTTP-layer wiring only — RouterSettingsService is mocked. Real upsert behavior is covered by
# tests/unit/test_router_settings_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _settings(**overrides):
    fields = dict(top_n=3, min_similarity=0.5, updated_at=datetime.now(timezone.utc))
    fields.update(overrides)
    return RouterSettings(**fields)


def test_get_status_returns_defaults(client, auth_headers):
    with patch(
        "app.presentation.routes.router_settings.RouterSettingsService.get_status",
        return_value=_settings(updated_at=None),
    ):
        response = client.get("/router-settings", headers=auth_headers("router_settings:read"))

    assert response.status_code == 200
    body = response.get_json()
    assert body["top_n"] == 3
    assert body["min_similarity"] == 0.5


def test_update_out_of_bounds_top_n_returns_400(client, auth_headers):
    response = client.put(
        "/router-settings",
        json={"top_n": 0, "min_similarity": 0.5},
        headers=auth_headers("router_settings:write"),
    )

    assert response.status_code == 400


def test_update_out_of_bounds_min_similarity_returns_400(client, auth_headers):
    response = client.put(
        "/router-settings",
        json={"top_n": 3, "min_similarity": 1.5},
        headers=auth_headers("router_settings:write"),
    )

    assert response.status_code == 400


def test_update_success_returns_updated_values(client, auth_headers):
    with patch(
        "app.presentation.routes.router_settings.RouterSettingsService.update",
        return_value=_settings(top_n=5),
    ):
        response = client.put(
            "/router-settings",
            json={"top_n": 5, "min_similarity": 0.5},
            headers=auth_headers("router_settings:write"),
        )

    assert response.status_code == 200
    assert response.get_json()["top_n"] == 5


def test_missing_auth_returns_401(client):
    response = client.get("/router-settings")
    assert response.status_code == 401
