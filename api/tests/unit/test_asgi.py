from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from api import create_app
from api.domain.entities import Identity
from api.presentation.web.asgi_bridge import build_asgi_app

# The one empirically-unverified assumption the MCP-merge redesign rests on: that wrapping Flask
# via a2wsgi.WSGIMiddleware and mounting it under Starlette preserves session cookies/CSRF exactly
# as gunicorn's own gthread workers already do. WSGI-in-ASGI operates purely at the transport
# layer and never touches Flask's internal request handling, so this was expected to just work —
# this test is the actual proof, not an assumption.
#
# HTTP-layer only, same as test_login_routes.py: AuthService is mocked, no real DB involved (the
# thing under test is the ASGI/WSGI bridge itself, not login business logic).


def _identity(**overrides):
    fields = dict(
        id=uuid4(),
        email="admin",
        name="Admin",
        password_hash="hashed",
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
        last_active_at=None,
    )
    fields.update(overrides)
    return Identity(**fields)


@pytest.fixture()
def client():
    flask_app = create_app(testing=True)
    asgi_app = build_asgi_app(flask_app)
    return TestClient(asgi_app)


def test_health_route_reachable_through_bridge(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_session_cookie_and_csrf_survive_the_bridge(client):
    login_page = client.get("/sign-in")
    assert login_page.status_code == 200
    assert "__CSRF_TOKEN__" in login_page.text

    csrf = login_page.text.split('window.__CSRF_TOKEN__="')[1].split('"')[0]

    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity()),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[uuid4()]),
    ):
        login_response = client.post(
            "/sign-in", json={"email": "admin", "password": "admin"}, headers={"X-CSRF-Token": csrf}
        )
    assert login_response.status_code == 200
    assert login_response.json()["redirect"] == "/"

    # No cookies passed explicitly — TestClient persists them across requests the same way a real
    # browser or gunicorn-served session would, proving the session Flask set on the login response
    # above survived being routed back out through the ASGI/WSGI bridge and back in on this request.
    change_password_page = client.get("/change-password")
    assert change_password_page.status_code == 200


def test_wrong_csrf_still_rejected_through_bridge(client):
    login_page = client.get("/sign-in")
    csrf = login_page.text.split('window.__CSRF_TOKEN__="')[1].split('"')[0]
    assert csrf

    with patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity()):
        response = client.post(
            "/sign-in", json={"email": "admin", "password": "admin"}, headers={"X-CSRF-Token": "wrong-token"}
        )
    assert response.status_code == 401
