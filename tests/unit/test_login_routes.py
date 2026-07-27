from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import User
from app.domain.errors import AuthenticationError

# HTTP-layer only — AuthService is mocked. Real password-hash/DB behavior is covered by
# tests/integration/test_auth_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _user(**overrides):
    fields = dict(
        id=uuid4(),
        username="admin",
        password_hash="hashed",
        must_change_password=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return User(**fields)


def _with_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Log in" in response.data


def test_login_success_redirects_to_change_password_when_required(client):
    csrf = _with_csrf(client)
    with patch("app.presentation.routes.auth_ui.AuthService.login", return_value=_user(must_change_password=True)):
        response = client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": csrf})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/change-password")


def test_login_success_redirects_to_dashboard_when_password_already_changed(client):
    csrf = _with_csrf(client)
    with patch("app.presentation.routes.auth_ui.AuthService.login", return_value=_user(must_change_password=False)):
        response = client.post("/login", data={"username": "admin", "password": "x", "csrf_token": csrf})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_wrong_credentials_shows_error(client):
    csrf = _with_csrf(client)
    with patch("app.presentation.routes.auth_ui.AuthService.login", side_effect=AuthenticationError("Invalid username or password.")):
        response = client.post("/login", data={"username": "admin", "password": "wrong", "csrf_token": csrf})
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data


def test_login_missing_csrf_rejected(client):
    _with_csrf(client)
    with patch("app.presentation.routes.auth_ui.AuthService.login", return_value=_user()):
        response = client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": "wrong-token"})
    assert response.status_code == 400


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_change_password_requires_login(client):
    response = client.get("/change-password")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def test_change_password_mismatch_shows_error(client):
    csrf = _logged_in(client)
    response = client.post(
        "/change-password",
        data={"new_password": "a-strong-password", "confirm_password": "a-different-password", "csrf_token": csrf},
    )
    assert response.status_code == 400
    assert b"do not match" in response.data


def test_change_password_too_short_shows_error(client):
    csrf = _logged_in(client)
    response = client.post(
        "/change-password",
        data={"new_password": "short", "confirm_password": "short", "csrf_token": csrf},
    )
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data


def test_change_password_success_redirects_to_dashboard(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.AuthService.change_password") as change_password:
        response = client.post(
            "/change-password",
            data={"new_password": "a-strong-password", "confirm_password": "a-strong-password", "csrf_token": csrf},
        )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    change_password.assert_called_once()
