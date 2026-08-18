from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Identity
from api.domain.errors import AuthenticationError

# HTTP-layer only — AuthService is mocked. Real password-hash/DB behavior is covered by
# tests/integration/test_auth_service.py. /login and /change-password serve the React SPA shell
# on GET and a JSON API on POST (webui/src/pages/LoginPage.tsx, ChangePasswordPage.tsx) — CSRF
# travels via the X-CSRF-Token header, not a form field.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _identity(**overrides):
    fields = dict(
        id=uuid4(),
        email="admin",
        name="Admin",
        password_hash="hashed",
        must_change_password=True,
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
        last_active_at=None,
    )
    fields.update(overrides)
    return Identity(**fields)


def _with_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def test_login_page_renders(client, tmp_path):
    # serve_spa_shell() reads the built webui/ output from static_folder — api/static/workspace/
    # is a gitignored build artifact, not guaranteed to exist on a fresh checkout/CI runner, so
    # this points static_folder at a stand-in index.html rather than depending on a local build.
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "index.html").write_text("<html><head><title>Workspace</title></head><body></body></html>")
    with client.application.app_context():
        client.application.static_folder = str(tmp_path)

    response = client.get("/login")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data


def test_login_success_redirects_to_change_password_when_required(client):
    csrf = _with_csrf(client)
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity(must_change_password=True)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[(uuid4(), "admin")]),
    ):
        response = client.post(
            "/login", json={"email": "admin", "password": "admin"}, headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 200
    assert response.get_json()["redirect"].endswith("/change-password")


def test_login_success_redirects_to_workspace_when_password_already_changed(client):
    csrf = _with_csrf(client)
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity(must_change_password=False)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[(uuid4(), "admin")]),
    ):
        response = client.post("/login", json={"email": "admin", "password": "x"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.get_json()["redirect"].endswith("/workspace")


def test_login_wrong_credentials_shows_error(client):
    csrf = _with_csrf(client)
    with patch(
        "api.presentation.routes.auth_ui.AuthService.login",
        side_effect=AuthenticationError("Invalid email or password."),
    ):
        response = client.post(
            "/login", json={"email": "admin", "password": "wrong"}, headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_login_missing_csrf_rejected(client):
    _with_csrf(client)
    with patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity()):
        response = client.post(
            "/login", json={"email": "admin", "password": "admin"}, headers={"X-CSRF-Token": "wrong-token"}
        )
    assert response.status_code == 401


def test_change_password_requires_login(client):
    response = client.get("/change-password")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def test_change_password_mismatch_shows_error(client):
    csrf = _logged_in(client)
    response = client.post(
        "/change-password",
        json={"new_password": "a-strong-password", "confirm_password": "a-different-password"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert b"do not match" in response.data


def test_change_password_too_short_shows_error(client):
    csrf = _logged_in(client)
    response = client.post(
        "/change-password",
        json={"new_password": "short", "confirm_password": "short"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data


def test_change_password_success_redirects_to_workspace(client):
    csrf = _logged_in(client)
    with patch("api.presentation.routes.auth_ui.AuthService.change_password") as change_password:
        response = client.post(
            "/change-password",
            json={"new_password": "a-strong-password", "confirm_password": "a-strong-password"},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 200
    assert response.get_json()["redirect"].endswith("/workspace")
    change_password.assert_called_once()
