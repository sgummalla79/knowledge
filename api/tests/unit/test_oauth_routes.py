from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import unquote
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Application, ApplicationOAuthClient
from api.domain.errors import AuthenticationError, ValidationError

# HTTP-layer wiring only — OAuthAuthorizationService is mocked. POST /oauth/token speaks standard
# OAuth 2.0 (form-encoded request, JSON {access_token,...}/{error,...} response), not this app's
# usual {"error": {"code","message","field"}} envelope — see the route module's docstring.
# GET /oauth/authorize-context + POST /oauth/authorize is browser/session-facing and is tested
# separately below.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


# ── POST /oauth/token ────────────────────────────────────────────────────────────────────────


def test_missing_grant_type_returns_oauth_error(client):
    response = client.post("/oauth/token", data={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "unsupported_grant_type"


def test_genuinely_unsupported_grant_type_returns_oauth_error(client):
    response = client.post("/oauth/token", data={"grant_type": "password"})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "unsupported_grant_type"
    assert "error_description" in body


def test_malformed_client_id_returns_invalid_client(client):
    response = client.post(
        "/oauth/token", data={"grant_type": "client_credentials", "client_id": "not-a-uuid", "client_secret": "x"}
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "invalid_client"


def test_wrong_secret_returns_invalid_client(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.issue_client_credentials_token",
        side_effect=AuthenticationError("bad secret"),
    ):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials", "client_id": str(uuid4()), "client_secret": "wrong"},
        )

    assert response.status_code == 401
    body = response.get_json()
    assert body["error"] == "invalid_client"
    assert "error_description" in body


def test_client_credentials_returns_access_token(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.issue_client_credentials_token",
        return_value="a.jwt.token",
    ):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials", "client_id": str(uuid4()), "client_secret": "correct"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["access_token"] == "a.jwt.token"
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 15 * 60
    assert "refresh_token" not in body


def test_token_endpoint_ignores_session_and_csrf(client):
    # No session cookie, no X-CSRF-Token header at all — this is a machine-to-machine,
    # credential-in-body endpoint, deliberately not gated like the rest of this app's JSON API.
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.issue_client_credentials_token",
        return_value="a.jwt.token",
    ):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials", "client_id": str(uuid4()), "client_secret": "correct"},
        )

    assert response.status_code == 200


def test_authorization_code_exchange_returns_access_and_refresh_token(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.exchange_authorization_code",
        return_value=("a.jwt.token", "a-refresh-token"),
    ):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "somecode",
                "redirect_uri": "http://127.0.0.1:9999/callback",
                "client_id": str(uuid4()),
                "code_verifier": "verifier",
            },
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["access_token"] == "a.jwt.token"
    assert body["refresh_token"] == "a-refresh-token"


def test_authorization_code_exchange_without_offline_access_omits_refresh_token(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.exchange_authorization_code",
        return_value=("a.jwt.token", None),
    ):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "somecode",
                "redirect_uri": "http://127.0.0.1:9999/callback",
                "client_id": str(uuid4()),
                "code_verifier": "verifier",
            },
        )

    assert response.status_code == 200
    assert "refresh_token" not in response.get_json()


def test_authorization_code_exchange_invalid_grant_returns_oauth_error(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.exchange_authorization_code",
        side_effect=ValidationError("validation_error", "Invalid, expired, or already-used grant."),
    ):
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "bad",
                "redirect_uri": "http://127.0.0.1:9999/callback",
                "client_id": str(uuid4()),
                "code_verifier": "verifier",
            },
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_grant"


def test_refresh_token_grant_returns_new_access_token(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.refresh_access_token", return_value="new.jwt.token"
    ):
        response = client.post(
            "/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "rt", "client_id": str(uuid4())}
        )

    assert response.status_code == 200
    assert response.get_json()["access_token"] == "new.jwt.token"


def test_refresh_token_grant_invalid_returns_oauth_error(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.refresh_access_token",
        side_effect=ValidationError("validation_error", "Invalid, expired, or already-used grant."),
    ):
        response = client.post(
            "/oauth/token", data={"grant_type": "refresh_token", "refresh_token": "bad", "client_id": str(uuid4())}
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_grant"


# ── GET /oauth/authorize-context + POST /oauth/authorize ────────────────────────────────────


def _application(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="MCP client",
        description=None,
        auth_method="oauth_authorization_code",
        status="active",
        service_identity_id=uuid4(),
        execute_as_identity_id=None,
        mcp_access=False,
        api_access=True,
        created_by=None,
        last_modified_by=None,
        revoked_at=None,
        revoked_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Application(**fields)


def _oauth_client(application_id, **overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        application_id=application_id,
        client_secret_hash=None,
        redirect_uris=["http://127.0.0.1:9999/callback"],
        created_at=now,
        last_rotated_at=now,
        revoked_at=None,
    )
    fields.update(overrides)
    return ApplicationOAuthClient(**fields)


_VALID_QS = "response_type=code&code_challenge=abc123&code_challenge_method=S256&redirect_uri=http://127.0.0.1:9999/callback"


def test_authorize_context_invalid_client_returns_error_not_redirect(client):
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
        side_effect=AuthenticationError("no such client"),
    ):
        response = client.get(f"/oauth/authorize-context?client_id={uuid4()}&{_VALID_QS}")

    assert response.status_code == 200
    body = response.get_json()
    assert "error" in body
    assert "authorize" not in body


def test_authorize_context_unregistered_redirect_uri_returns_error(client):
    application = _application()
    oauth_client = _oauth_client(application.id, redirect_uris=["http://127.0.0.1:1111/other"])
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
        return_value=(application, oauth_client),
    ):
        response = client.get(f"/oauth/authorize-context?client_id={application.id}&{_VALID_QS}")

    assert response.status_code == 200
    assert "error" in response.get_json()


def test_authorize_context_bad_response_type_returns_redirect_to_trusted_redirect_uri(client):
    application = _application()
    oauth_client = _oauth_client(application.id)
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
        return_value=(application, oauth_client),
    ):
        response = client.get(
            f"/oauth/authorize-context?client_id={application.id}&response_type=token&code_challenge=abc&code_challenge_method=S256&redirect_uri=http://127.0.0.1:9999/callback"
        )

    assert response.status_code == 200
    redirect = response.get_json()["redirect"]
    assert redirect.startswith("http://127.0.0.1:9999/callback?")
    assert "error=invalid_request" in redirect


def test_authorize_context_not_logged_in_returns_sign_in_redirect(client):
    application = _application()
    oauth_client = _oauth_client(application.id)
    with patch(
        "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
        return_value=(application, oauth_client),
    ):
        response = client.get(f"/oauth/authorize-context?client_id={application.id}&{_VALID_QS}")

    assert response.status_code == 200
    redirect = response.get_json()["redirect"]
    assert redirect.startswith("/sign-in")
    # The `next` param must point back at the real consent *page* (/oauth/authorize), not this
    # JSON endpoint's own path (/oauth/authorize-context) — a real bug found via end-to-end
    # verification this session (see this repo's Phase B history): signing in via a `next` that
    # pointed at -context would land the browser on raw JSON instead of the consent screen.
    next_param = redirect.split("next=", 1)[1]
    assert unquote(next_param).startswith("/oauth/authorize?")
    assert "authorize-context" not in unquote(next_param)


def test_authorize_context_not_an_org_member_returns_error(client):
    application = _application()
    oauth_client = _oauth_client(application.id)
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
    with (
        patch(
            "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
            return_value=(application, oauth_client),
        ),
        patch("api.presentation.routes.oauth.OrgMemberRepository.get", return_value=None),
    ):
        response = client.get(f"/oauth/authorize-context?client_id={application.id}&{_VALID_QS}")

    assert response.status_code == 200
    assert "error" in response.get_json()


def test_authorize_context_logged_in_member_returns_authorize_data(client):
    application = _application()
    oauth_client = _oauth_client(application.id)
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
    with (
        patch(
            "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
            return_value=(application, oauth_client),
        ),
        patch("api.presentation.routes.oauth.OrgMemberRepository.get", return_value="a-membership"),
        patch("api.presentation.routes.oauth.OrganizationRepository.get", return_value=None),
    ):
        response = client.get(f"/oauth/authorize-context?client_id={application.id}&{_VALID_QS}")

    assert response.status_code == 200
    body = response.get_json()
    assert "authorize" in body
    assert body["authorize"]["application_name"] == application.name


def test_authorize_post_requires_login(client):
    response = client.post("/oauth/authorize", json={})

    assert response.status_code == 401


def test_authorize_post_deny_returns_access_denied_redirect(client):
    application = _application()
    oauth_client = _oauth_client(application.id)
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf"
    with (
        patch(
            "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
            return_value=(application, oauth_client),
        ),
        patch("api.presentation.routes.oauth.OrgMemberRepository.get", return_value="a-membership"),
    ):
        response = client.post(
            "/oauth/authorize",
            headers={"X-CSRF-Token": "test-csrf"},
            json={
                "client_id": str(application.id),
                "redirect_uri": "http://127.0.0.1:9999/callback",
                "response_type": "code",
                "code_challenge": "abc123",
                "code_challenge_method": "S256",
                "state": "xyz",
                "allow": False,
            },
        )

    assert response.status_code == 200
    body = response.get_json()
    assert "error=access_denied" in body["redirect"]
    assert "state=xyz" in body["redirect"]


def test_authorize_post_allow_returns_code_redirect(client):
    application = _application()
    oauth_client = _oauth_client(application.id)
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf"
    with (
        patch(
            "api.presentation.routes.oauth.OAuthAuthorizationService.get_authorization_code_client",
            return_value=(application, oauth_client),
        ),
        patch("api.presentation.routes.oauth.OrgMemberRepository.get", return_value="a-membership"),
        patch(
            "api.presentation.routes.oauth.OAuthAuthorizationService.create_authorization_code",
            return_value="the-raw-code",
        ),
    ):
        response = client.post(
            "/oauth/authorize",
            headers={"X-CSRF-Token": "test-csrf"},
            json={
                "client_id": str(application.id),
                "redirect_uri": "http://127.0.0.1:9999/callback",
                "response_type": "code",
                "code_challenge": "abc123",
                "code_challenge_method": "S256",
                "state": "xyz",
                "allow": True,
            },
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["redirect"] == "http://127.0.0.1:9999/callback?code=the-raw-code&state=xyz"


def test_authorize_post_wrong_csrf_returns_401(client):
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf"
    response = client.post("/oauth/authorize", headers={"X-CSRF-Token": "wrong"}, json={"allow": True})

    assert response.status_code == 401


# ── discovery ────────────────────────────────────────────────────────────────────────────────


def test_discovery_endpoint(client):
    response = client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    body = response.get_json()
    assert body["token_endpoint"].endswith("/oauth/token")
    assert body["authorization_endpoint"].endswith("/oauth/authorize")
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert "authorization_code" in body["grant_types_supported"]


def test_discovery_endpoint_honors_external_base_url_override(client):
    # A reverse proxy that terminates TLS and mounts this app under a path prefix (e.g. this
    # repo's Hostinger Traefik ingress) makes request.url_root wrong on both counts — see
    # DEFAULT_EXTERNAL_BASE_URL's own comment (api/constants.py).
    with patch("api.presentation.routes.oauth.config.external_base_url", "https://api.example.com/knowledge"):
        response = client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    body = response.get_json()
    assert body["issuer"] == "https://api.example.com/knowledge"
    assert body["token_endpoint"] == "https://api.example.com/knowledge/oauth/token"
    assert body["authorization_endpoint"] == "https://api.example.com/knowledge/oauth/authorize"
