from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import User

# HTTP-layer only — no service is exercised beyond auth gating, since api_docs.html is static
# content with no dynamic data.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def _user(**overrides):
    from datetime import datetime, timezone

    fields = dict(
        id=uuid4(),
        username="admin",
        password_hash="hashed",
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return User(**fields)


def test_api_docs_requires_login(client):
    response = client.get("/api-docs")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_api_docs_renders_for_logged_in_user(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user()):
        response = client.get("/api-docs")
    assert response.status_code == 200
    assert b"API Documentation" in response.data
    assert b"/oauth/token" in response.data


def test_api_docs_links_back_to_dashboard(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user()):
        response = client.get("/api-docs")
    assert b'href="/dashboard"' in response.data


def test_api_docs_redirects_to_change_password_when_required(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user(must_change_password=True)):
        response = client.get("/api-docs")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/change-password")


@patch("app.presentation.routes.auth_ui.RefreshTokenRepository.find_current_for_application", return_value=None)
@patch("app.presentation.routes.auth_ui.ApplicationService.list_applications", return_value=[])
def test_dashboard_links_to_api_docs_and_configuration(_list_apps, _find_token, client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user()):
        response = client.get("/dashboard")
    assert response.status_code == 200
    assert b'href="/api-docs"' in response.data
    assert b'href="/dashboard/configuration"' in response.data
    assert b"Registered Applications" in response.data
    assert b"Configuration" in response.data


def test_api_docs_sidebar_links_to_configuration(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user()):
        response = client.get("/api-docs")
    assert b'href="/dashboard/configuration"' in response.data
