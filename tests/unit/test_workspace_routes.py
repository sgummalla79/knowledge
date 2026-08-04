from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app

# HTTP-layer only — TokenService/UserRepository are mocked, no real DB involved. Mirrors
# tests/unit/test_application_routes.py's pattern.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def test_dashboard_token_requires_login(client):
    response = client.post("/dashboard/token")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_dashboard_token_requires_valid_csrf(client):
    _logged_in(client)
    response = client.post("/dashboard/token", headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 401


def test_dashboard_token_mints_an_access_token(client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.workspace.TokenService.client_credentials_grant",
        return_value={"access_token": "minted-token", "expires_in": 3600, "token_type": "Bearer", "scope": "x"},
    ) as grant:
        response = client.post("/dashboard/token", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    body = response.get_json()
    assert body == {"access_token": "minted-token", "expires_in": 3600}
    grant.assert_called_once()


def test_workspace_requires_login(client):
    response = client.get("/workspace")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@patch("app.presentation.routes.workspace.UserRepository.get", return_value=None)
def test_workspace_serves_built_shell_with_injected_csrf_token(_get_user, client, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "index.html").write_text("<html><head><title>Workspace</title></head><body></body></html>")

    with client.application.app_context():
        client.application.static_folder = str(tmp_path)

    _logged_in(client)
    response = client.get("/workspace")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data


@patch("app.presentation.routes.workspace.UserRepository.get", return_value=None)
def test_workspace_missing_build_output_returns_503(_get_user, client, tmp_path):
    with client.application.app_context():
        client.application.static_folder = str(tmp_path)

    _logged_in(client)
    response = client.get("/workspace")
    assert response.status_code == 503


def test_settings_requires_login(client):
    response = client.get("/settings")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@patch("app.presentation.routes.workspace.UserRepository.get", return_value=None)
def test_settings_serves_built_shell_with_injected_csrf_token(_get_user, client, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "index.html").write_text("<html><head><title>Workspace</title></head><body></body></html>")

    with client.application.app_context():
        client.application.static_folder = str(tmp_path)

    _logged_in(client)
    response = client.get("/settings")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data
