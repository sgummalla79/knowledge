from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Identity
from api.domain.errors import AuthenticationError

# HTTP-layer only — AuthService is mocked. Real password-hash/DB behavior is covered by
# tests/integration/test_auth_service.py. /sign-in, /sign-up and /change-password serve the React
# SPA shell on GET and a JSON API on POST — CSRF travels via the X-CSRF-Token header, not a form
# field.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _identity(**overrides):
    fields = dict(
        id=uuid4(),
        username="admin@local",
        email=None,
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


def test_sign_in_page_renders(client, tmp_path):
    # serve_spa_shell() reads the built webui/ output from static_folder — api/static/workspace/
    # is a gitignored build artifact, not guaranteed to exist on a fresh checkout/CI runner, so
    # this points static_folder at a stand-in index.html rather than depending on a local build.
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "index.html").write_text("<html><head><title>Knowledge</title></head><body></body></html>")
    with client.application.app_context():
        client.application.static_folder = str(tmp_path)

    response = client.get("/sign-in")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data


def test_sign_up_page_renders(client, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "index.html").write_text("<html><head><title>Knowledge</title></head><body></body></html>")
    with client.application.app_context():
        client.application.static_folder = str(tmp_path)

    response = client.get("/sign-up")
    assert response.status_code == 200
    assert b"__CSRF_TOKEN__" in response.data


def test_sign_in_success_redirects_to_change_password_when_required(client):
    csrf = _with_csrf(client)
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity(must_change_password=True)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[(uuid4(), "admin")]),
    ):
        response = client.post(
            "/sign-in", json={"username": "admin@local", "password": "admin"}, headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 200
    assert response.get_json()["redirect"].endswith("/change-password")


def test_sign_in_success_redirects_home_when_password_already_changed(client):
    csrf = _with_csrf(client)
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity(must_change_password=False)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[(uuid4(), "admin")]),
    ):
        response = client.post("/sign-in", json={"username": "admin@local", "password": "x"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.get_json()["redirect"] == "/"


def test_sign_in_wrong_credentials_shows_error(client):
    csrf = _with_csrf(client)
    with patch(
        "api.presentation.routes.auth_ui.AuthService.login",
        side_effect=AuthenticationError("Invalid username or password."),
    ):
        response = client.post(
            "/sign-in", json={"username": "admin@local", "password": "wrong"}, headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data


def test_sign_in_missing_csrf_rejected(client):
    _with_csrf(client)
    with patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity()):
        response = client.post(
            "/sign-in", json={"username": "admin@local", "password": "admin"}, headers={"X-CSRF-Token": "wrong-token"}
        )
    assert response.status_code == 401


def test_sign_up_missing_csrf_rejected(client):
    _with_csrf(client)
    response = client.post(
        "/sign-up",
        json={"username": "new@acme.com", "password": "a-strong-password", "name": "Ada"},
        headers={"X-CSRF-Token": "wrong-token"},
    )
    assert response.status_code == 401


def test_sign_up_short_password_shows_error(client):
    csrf = _with_csrf(client)
    response = client.post(
        "/sign-up",
        json={"username": "new@acme.com", "password": "short", "name": "Ada"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert b"at least 8 characters" in response.data


def test_sign_up_success_redirects_home(client):
    csrf = _with_csrf(client)
    identity = _identity(must_change_password=False)
    with (
        patch("api.presentation.routes.auth_ui.SignupService.signup", return_value=(identity, None)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[(uuid4(), "admin")]),
    ):
        response = client.post(
            "/sign-up",
            json={
                "username": "new@acme.com",
                "password": "a-strong-password",
                "name": "Ada",
                "org_name": "ada-labs",
            },
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 200
    assert response.get_json()["redirect"] == "/"


def test_sign_up_invalid_org_name_shows_error(client):
    csrf = _with_csrf(client)
    response = client.post(
        "/sign-up",
        json={
            "username": "new@acme.com",
            "password": "a-strong-password",
            "name": "Ada",
            "org_name": "Not Slug!",
            "email": "new-contact@acme.com",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "organization_name_invalid"
    assert body["error"]["field"] == "org_name"


def test_sign_up_invalid_username_shows_error(client):
    csrf = _with_csrf(client)
    response = client.post(
        "/sign-up",
        json={"username": "not-an-email", "password": "a-strong-password", "name": "Ada", "org_name": "ada-labs"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "username_invalid_format"
    assert body["error"]["field"] == "username"


def test_sign_up_missing_email_shows_error(client):
    csrf = _with_csrf(client)
    response = client.post(
        "/sign-up",
        json={"username": "new@acme.com", "password": "a-strong-password", "name": "Ada", "org_name": "ada-labs"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "email_invalid_format"
    assert body["error"]["field"] == "email"


def test_check_org_name_available(client):
    with patch(
        "api.presentation.routes.auth_ui.OrganizationRepository.get_by_slug", return_value=None
    ):
        response = client.get("/check-org-name", query_string={"name": "ada-labs"})
    assert response.status_code == 200
    assert response.get_json() == {"available": True, "message": None}


def test_check_org_name_taken(client):
    with patch(
        "api.presentation.routes.auth_ui.OrganizationRepository.get_by_slug", return_value=object()
    ):
        response = client.get("/check-org-name", query_string={"name": "ada-labs"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["available"] is False
    assert "taken" in body["message"]


def test_check_org_name_invalid_format(client):
    response = client.get("/check-org-name", query_string={"name": "Not Valid!"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["available"] is False
    assert body["message"]


def test_check_org_name_reserved(client):
    response = client.get("/check-org-name", query_string={"name": "admin"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["available"] is False
    assert "reserved" in body["message"]


def test_change_password_requires_login(client):
    response = client.get("/change-password")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sign-in")


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


def test_change_password_success_redirects_home(client):
    csrf = _logged_in(client)
    with patch("api.presentation.routes.auth_ui.AuthService.change_password") as change_password:
        response = client.post(
            "/change-password",
            json={"new_password": "a-strong-password", "confirm_password": "a-strong-password"},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 200
    assert response.get_json()["redirect"] == "/"
    change_password.assert_called_once()
