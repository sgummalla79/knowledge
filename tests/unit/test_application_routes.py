from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.constants import DEFAULT_DASHBOARD_APPLICATION_ID, DEFAULT_MCP_APPLICATION_ID
from app.domain.entities import Application
from app.domain.errors import ValidationError

# HTTP-layer only — ApplicationService is mocked. Real register/regenerate/revoke behavior is
# covered by tests/integration/test_application_service.py. Applications management is
# session+CSRF authenticated JSON (see app/presentation/routes/auth_ui.py's _require_csrf_header),
# never the bearer-token OAuth2 API surface — CSRF travels via the X-CSRF-Token header, matching
# /dashboard/token and /change-password.


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
        name="mcp-server",
        allowed_scopes=["libraries:read", "query:execute"],
        created_at=datetime.now(timezone.utc),
        redirect_uris=[],
    )
    fields.update(overrides)
    return Application(**fields)


def test_list_scopes_requires_login(client):
    response = client.get("/dashboard/scopes")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_list_scopes_groups_by_resource(client):
    _logged_in(client)
    response = client.get("/dashboard/scopes")
    assert response.status_code == 200
    body = response.get_json()
    labels = [group["label"] for group in body]
    assert "Libraries" in labels
    libraries_group = next(group for group in body if group["label"] == "Libraries")
    assert "libraries:read" in libraries_group["scopes"]


@patch("app.presentation.routes.auth_ui.RefreshTokenRepository.find_current_for_application", return_value=None)
def test_list_applications_hides_builtin_applications(_find_token, client):
    _logged_in(client)
    builtin_mcp = _application(id=DEFAULT_MCP_APPLICATION_ID, name="mcp-server (built-in)")
    builtin_dashboard = _application(id=DEFAULT_DASHBOARD_APPLICATION_ID, name="dashboard (built-in)")
    visible = _application(name="knowledge-store")
    with patch(
        "app.presentation.routes.auth_ui.ApplicationService.list_applications",
        return_value=[builtin_mcp, builtin_dashboard, visible],
    ):
        response = client.get("/dashboard/applications")
    assert response.status_code == 200
    names = [row["name"] for row in response.get_json()]
    assert names == ["knowledge-store"]


def test_register_application_returns_secret_once(client):
    csrf = _logged_in(client)
    application = _application()
    with patch(
        "app.presentation.routes.auth_ui.ApplicationService.register", return_value=("raw-secret-value", application)
    ):
        response = client.post(
            "/dashboard/applications",
            json={"name": "mcp-server", "scopes": ["libraries:read", "query:execute"]},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 200
    body = response.get_json()
    assert body["client_secret"] == "raw-secret-value"
    assert body["name"] == "mcp-server"


def test_register_application_duplicate_name_returns_error(client):
    csrf = _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.ApplicationService.register",
        side_effect=ValidationError(
            "application_name_taken", "An application named 'mcp-server' already exists.", field="name"
        ),
    ):
        response = client.post(
            "/dashboard/applications",
            json={"name": "mcp-server", "scopes": ["libraries:read"]},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_register_application_missing_csrf_rejected(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.register") as register:
        response = client.post(
            "/dashboard/applications",
            json={"name": "mcp-server", "scopes": ["libraries:read"]},
            headers={"X-CSRF-Token": "wrong"},
        )
    assert response.status_code == 401
    register.assert_not_called()


def test_revoke_token_succeeds(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.revoke_application_token") as revoke:
        response = client.post(
            f"/dashboard/applications/{uuid4()}/revoke-token", headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 204
    revoke.assert_called_once()


def test_delete_application_succeeds(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(f"/dashboard/applications/{uuid4()}/delete", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 204
    delete.assert_called_once()


def test_delete_application_missing_csrf_does_not_delete(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(f"/dashboard/applications/{uuid4()}/delete", headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 401
    delete.assert_not_called()


def test_delete_builtin_mcp_application_is_rejected(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(
            f"/dashboard/applications/{DEFAULT_MCP_APPLICATION_ID}/delete", headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 404
    delete.assert_not_called()


def test_revoke_token_builtin_mcp_application_is_rejected(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.revoke_application_token") as revoke:
        response = client.post(
            f"/dashboard/applications/{DEFAULT_MCP_APPLICATION_ID}/revoke-token", headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 404
    revoke.assert_not_called()


def test_delete_builtin_dashboard_application_is_rejected(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(
            f"/dashboard/applications/{DEFAULT_DASHBOARD_APPLICATION_ID}/delete", headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 404
    delete.assert_not_called()


def test_revoke_token_builtin_dashboard_application_is_rejected(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.revoke_application_token") as revoke:
        response = client.post(
            f"/dashboard/applications/{DEFAULT_DASHBOARD_APPLICATION_ID}/revoke-token", headers={"X-CSRF-Token": csrf}
        )
    assert response.status_code == 404
    revoke.assert_not_called()
