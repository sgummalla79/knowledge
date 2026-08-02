from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import Application
from app.domain.errors import InvalidRedirectUriError

# HTTP-layer only — AuthorizeService/ClientRegistrationService are mocked. Real behavior is
# covered by tests/integration/test_authorization_code_flow.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def _application(**overrides):
    fields = dict(
        id=uuid4(),
        name="claude-code",
        allowed_scopes=["libraries:read", "query:execute", "offline_access"],
        created_at=datetime.now(timezone.utc),
        redirect_uris=["http://127.0.0.1:9999/callback"],
    )
    fields.update(overrides)
    return Application(**fields)


def _authorize_query(**overrides):
    params = dict(
        response_type="code",
        client_id=str(uuid4()),
        redirect_uri="http://127.0.0.1:9999/callback",
        scope="libraries:read",
        state="xyz",
        code_challenge="abc123",
        code_challenge_method="S256",
    )
    params.update(overrides)
    return params


def test_authorize_get_requires_login(client):
    response = client.get("/oauth/authorize", query_string=_authorize_query())
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=")
    assert "%2Foauth%2Fauthorize" in response.headers["Location"] or "/oauth/authorize" in response.headers["Location"]


def test_authorize_get_renders_consent_screen(client):
    _logged_in(client)
    application = _application()
    with patch("app.presentation.routes.oauth.AuthorizeService.validate_request", return_value=application):
        response = client.get("/oauth/authorize", query_string=_authorize_query())
    assert response.status_code == 200
    assert b"claude-code" in response.data
    assert b"libraries:read" in response.data


def test_authorize_get_invalid_redirect_uri_renders_error_page_not_redirect(client):
    _logged_in(client)
    with patch(
        "app.presentation.routes.oauth.AuthorizeService.validate_request",
        side_effect=InvalidRedirectUriError(),
    ):
        response = client.get("/oauth/authorize", query_string=_authorize_query())
    assert response.status_code == 400
    assert b"redirect_uri" in response.data.lower() or b"client_id" in response.data.lower()


def test_authorize_post_approve_redirects_with_code(client):
    csrf = _logged_in(client)
    application = _application()
    with (
        patch("app.presentation.routes.oauth.AuthorizeService.validate_request", return_value=application),
        patch("app.presentation.routes.oauth.AuthorizeService.create_authorization_code", return_value="the-code"),
    ):
        response = client.post(
            "/oauth/authorize",
            data={**_authorize_query(), "csrf_token": csrf, "action": "approve"},
        )
    assert response.status_code == 302
    assert "code=the-code" in response.headers["Location"]
    assert "state=xyz" in response.headers["Location"]


def test_authorize_post_deny_redirects_with_access_denied(client):
    csrf = _logged_in(client)
    application = _application()
    with patch("app.presentation.routes.oauth.AuthorizeService.validate_request", return_value=application):
        response = client.post(
            "/oauth/authorize",
            data={**_authorize_query(), "csrf_token": csrf, "action": "deny"},
        )
    assert response.status_code == 302
    assert "error=access_denied" in response.headers["Location"]


def test_authorize_post_missing_csrf_rejected(client):
    _logged_in(client)
    response = client.post(
        "/oauth/authorize",
        data={**_authorize_query(), "csrf_token": "wrong", "action": "approve"},
    )
    assert response.status_code == 400


def test_register_client_returns_credentials(client):
    application = _application(redirect_uris=["http://127.0.0.1:9999/callback"])
    with patch(
        "app.presentation.routes.oauth.ClientRegistrationService.register_client",
        return_value=("raw-secret-value", application),
    ):
        response = client.post(
            "/oauth/register",
            json={"client_name": "claude-code", "redirect_uris": ["http://127.0.0.1:9999/callback"]},
        )
    assert response.status_code == 201
    body = response.get_json()
    assert body["client_id"] == str(application.id)
    assert body["client_secret"] == "raw-secret-value"
    assert body["redirect_uris"] == ["http://127.0.0.1:9999/callback"]


def test_well_known_authorization_server_metadata(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    body = response.get_json()
    assert body["authorization_endpoint"].endswith("/oauth/authorize")
    assert body["token_endpoint"].endswith("/oauth/token")
    assert body["registration_endpoint"].endswith("/oauth/register")
    assert "authorization_code" in body["grant_types_supported"]
    assert body["code_challenge_methods_supported"] == ["S256"]
