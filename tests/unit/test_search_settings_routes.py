from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from app.domain.entities import SearchSettings

# HTTP-layer wiring only — SearchSettingsService is mocked. Real upsert/RRF behavior is covered by
# tests/integration/test_retrieval_service.py and tests/unit/test_rrf.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _settings(**overrides):
    fields = dict(dense_k=20, sparse_k=20, rrf_k=60, updated_at=datetime.now(timezone.utc))
    fields.update(overrides)
    return SearchSettings(**fields)


def test_get_status_returns_defaults(client, auth_headers):
    with patch(
        "app.presentation.routes.search_settings.SearchSettingsService.get_status",
        return_value=_settings(updated_at=None),
    ):
        response = client.get("/search-settings", headers=auth_headers("search_settings:read"))

    assert response.status_code == 200
    body = response.get_json()
    assert body["dense_k"] == 20


def test_update_out_of_bounds_dense_k_returns_structured_400(client, auth_headers):
    response = client.put(
        "/search-settings",
        json={"dense_k": 0, "sparse_k": 20, "rrf_k": 60},
        headers=auth_headers("search_settings:write"),
    )

    assert response.status_code == 400


def test_update_success_returns_updated_values(client, auth_headers):
    with patch(
        "app.presentation.routes.search_settings.SearchSettingsService.update",
        return_value=_settings(dense_k=30),
    ):
        response = client.put(
            "/search-settings",
            json={"dense_k": 30, "sparse_k": 20, "rrf_k": 60},
            headers=auth_headers("search_settings:write"),
        )

    assert response.status_code == 200
    assert response.get_json()["dense_k"] == 30


def test_missing_auth_returns_401(client):
    response = client.get("/search-settings")
    assert response.status_code == 401
