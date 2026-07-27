import pytest

from app import create_app
from app.infrastructure.auth.jwt_tokens import issue_access_token


@pytest.fixture()
def app():
    return create_app(testing=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def test_missing_auth_returns_structured_401_envelope(client):
    response = client.get("/libraries")

    assert response.status_code == 401
    body = response.get_json()
    assert body["error"]["code"] == "unauthorized"


def test_bearer_token_with_required_scope_passes_auth(app, client):
    with app.app_context():
        token = issue_access_token("some-app-id", ["libraries:read"], ttl_seconds=60)
    response = client.get("/libraries", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401
    assert response.status_code != 403


def test_bearer_token_missing_required_scope_returns_403(app, client):
    with app.app_context():
        token = issue_access_token("some-app-id", ["query:execute"], ttl_seconds=60)
    response = client.get("/libraries", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "insufficient_scope"


def test_invalid_bearer_token_returns_401(client):
    response = client.get("/libraries", headers={"Authorization": "Bearer garbage.not-a.jwt"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthorized"


def test_route_with_no_specific_scope_accepts_any_valid_token(app, client):
    with app.app_context():
        token = issue_access_token("some-app-id", ["query:execute"], ttl_seconds=60)
    response = client.get("/embedding-options", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code != 401
    assert response.status_code != 403
