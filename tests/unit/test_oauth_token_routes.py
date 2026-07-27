from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.errors import InvalidClientError, InvalidGrantError, ValidationError

# HTTP-layer only — TokenService is mocked. Real grant behavior is covered by
# tests/integration/test_token_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_client_credentials_grant_success(client):
    result = {
        "access_token": "jwt-value",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "libraries:read query:execute",
    }
    with patch("app.presentation.routes.oauth.TokenService.client_credentials_grant", return_value=result):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": str(uuid4()),
                "client_secret": "secret",
                "scope": "libraries:read query:execute",
            },
        )
    assert response.status_code == 200
    assert response.get_json()["access_token"] == "jwt-value"


def test_client_credentials_grant_invalid_client(client):
    with patch(
        "app.presentation.routes.oauth.TokenService.client_credentials_grant",
        side_effect=InvalidClientError(),
    ):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": str(uuid4()),
                "client_secret": "wrong",
                "scope": "libraries:read",
            },
        )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_client"


def test_client_credentials_grant_malformed_client_id_returns_400(client):
    response = client.post(
        "/oauth/token",
        data={"grant_type": "client_credentials", "client_id": "not-a-uuid", "client_secret": "x", "scope": ""},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"


def test_client_credentials_grant_invalid_scope(client):
    with patch(
        "app.presentation.routes.oauth.TokenService.client_credentials_grant",
        side_effect=ValidationError("invalid_scope", "Scope(s) not allowed for this application: libraries:write.", field="scope"),
    ):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": str(uuid4()),
                "client_secret": "secret",
                "scope": "libraries:write",
            },
        )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_scope"


def test_refresh_token_grant_success(client):
    result = {"access_token": "jwt-value", "token_type": "Bearer", "expires_in": 3600, "scope": "libraries:read"}
    with patch("app.presentation.routes.oauth.TokenService.refresh_token_grant", return_value=result):
        response = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "some-token"})
    assert response.status_code == 200
    assert response.get_json()["access_token"] == "jwt-value"


def test_refresh_token_grant_invalid(client):
    with patch("app.presentation.routes.oauth.TokenService.refresh_token_grant", side_effect=InvalidGrantError()):
        response = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "bad"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_grant"


def test_unsupported_grant_type_returns_400(client):
    response = client.post("/oauth/token", data={"grant_type": "password"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "unsupported_grant_type"
