from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain import error_codes
from api.domain.entities import Identity, Organization
from api.domain.errors import AuthenticationError, ConflictError

# HTTP-layer only — AuthService is mocked. Real password-hash/DB behavior is covered by
# tests/integration/test_auth_service.py. /sign-in, /sign-up, /change-password are JSON-only POST
# actions now (see this repo's Phase A history — the GET-HTML-shell siblings are gone, this API
# renders no HTML) — CSRF travels via the X-CSRF-Token header, not a form field.


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


def _org(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        name="acme-labs",
        slug="acme-labs",
        description=None,
        plan="free",
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Organization(**fields)


def _with_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def test_sign_in_success_redirects_to_change_password_when_required(client):
    csrf = _with_csrf(client)
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity(must_change_password=True)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[uuid4()]),
    ):
        response = client.post(
            "/sign-in", json={"username": "admin@local", "password": "admin"}, headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 200
    assert response.get_json()["redirect"].endswith("/change-password")


def test_sign_in_success_redirects_home_when_password_already_changed(client):
    csrf = _with_csrf(client)
    org = _org()
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity(must_change_password=False)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[org.id]),
        patch("api.presentation.routes.auth_ui.OrganizationRepository.get", return_value=org),
    ):
        response = client.post("/sign-in", json={"username": "admin@local", "password": "x"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert response.get_json()["redirect"] == f"/{org.slug}"


def test_sign_in_success_refreshes_last_active_at(client):
    """Regression test for a real production lockout (2026-08-24): logging in must refresh
    last_active_at itself, not just subsequent authenticated requests (session_guard.py's
    resolve_cookie_session only reaches its own touch_last_active call after the inactivity check
    already passed) -- otherwise an identity whose last_active_at is already older than the org's
    inactivity_timeout_minutes can never log in again, since every fresh session immediately fails
    the same stale-timestamp check on its very next request."""
    csrf = _with_csrf(client)
    org = _org()
    identity = _identity(must_change_password=False)
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=identity),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[org.id]),
        patch("api.presentation.routes.auth_ui.OrganizationRepository.get", return_value=org),
        patch("api.presentation.routes.auth_ui.IdentityRepository.touch_last_active") as mock_touch,
    ):
        response = client.post("/sign-in", json={"username": "admin@local", "password": "x"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    mock_touch.assert_called_once_with(identity.id)


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
    org = _org(slug="ada-labs", name="ada-labs")
    with (
        patch("api.presentation.routes.auth_ui.SignupService.signup", return_value=(identity, None)),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[org.id]),
        patch("api.presentation.routes.auth_ui.OrganizationRepository.get", return_value=org),
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
    assert response.get_json()["redirect"] == "/ada-labs"


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
    # POST-only now (see this repo's Phase A history) — a JSON 401, not a browser redirect; this
    # API renders no sign-in page to redirect to.
    response = client.post("/change-password", json={"new_password": "x", "confirm_password": "x"})
    assert response.status_code == 401


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


# ── GET /csrf-token, GET /session (replace what serve_spa_shell used to embed — see Phase A) ────


def test_get_csrf_token_returns_token_and_sets_cookie(client):
    response = client.get("/csrf-token")
    assert response.status_code == 200
    token = response.get_json()["csrf_token"]
    assert token
    # Same token handed back on a second call within the same session — it's stored, not
    # regenerated per request.
    response2 = client.get("/csrf-token")
    assert response2.get_json()["csrf_token"] == token


def test_get_session_requires_login(client):
    response = client.get("/session")
    assert response.status_code == 401


def test_get_session_returns_identity_and_org(client):
    identity = _identity(must_change_password=False)
    org = _org()
    with client.session_transaction() as sess:
        sess["identity_id"] = str(identity.id)
        sess["active_org_id"] = str(org.id)
    with (
        patch("api.presentation.routes.auth_ui.IdentityRepository.get_by_id", return_value=identity),
        patch("api.presentation.routes.auth_ui.OrganizationRepository.get", return_value=org),
    ):
        response = client.get("/session")
    assert response.status_code == 200
    body = response.get_json()
    assert body["username"] == identity.username
    assert body["org_id"] == str(org.id)
    assert body["org_slug"] == org.slug


# ── PII exclusion from logs (security review, see this repo's Phase A history) ──────────────────


def test_duplicate_username_signup_error_message_is_not_logged(client, caplog):
    # IDENTITY_USERNAME_TAKEN's message embeds the attempted username (email-shaped, i.e. PII) —
    # error_handlers.py's DomainError handler must log only error.code, never error.message, so
    # this never reaches the logs even though the HTTP response body still legitimately includes
    # it (the caller already knows what they just typed).
    csrf = _with_csrf(client)
    taken_username = "someone-secret@example.com"
    with (
        patch(
            "api.presentation.routes.auth_ui.SignupService.signup",
            side_effect=ConflictError(
                error_codes.IDENTITY_USERNAME_TAKEN,
                f"An account with username '{taken_username}' already exists.",
                field="username",
            ),
        ),
        caplog.at_level("DEBUG"),
    ):
        response = client.post(
            "/sign-up",
            json={"username": taken_username, "password": "a-strong-password", "name": "Ada", "org_name": "ada-labs"},
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 409
    # The response body legitimately still contains it — this is not the leak being guarded against.
    assert taken_username in response.get_json()["error"]["message"]
    # But no log record anywhere should contain it.
    for record in caplog.records:
        assert taken_username not in record.getMessage()
