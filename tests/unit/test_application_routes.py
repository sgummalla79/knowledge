from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.constants import DEFAULT_MCP_APPLICATION_ID
from app.domain.entities import Application
from app.domain.errors import ValidationError

# HTTP-layer only — ApplicationService is mocked. Real register/regenerate/revoke behavior is
# covered by tests/integration/test_application_service.py.


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


@patch("app.presentation.routes.auth_ui.RefreshTokenRepository.find_current_for_application", return_value=None)
@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
def test_register_application_shows_secret_once(_get_user, _find_token, client):
    csrf = _logged_in(client)
    application = _application()
    with (
        patch("app.presentation.routes.auth_ui.ApplicationService.register", return_value=("raw-secret-value", application)),
        patch("app.presentation.routes.auth_ui.ApplicationService.list_applications", return_value=[application]),
    ):
        response = client.post(
            "/dashboard/applications",
            data={"name": "mcp-server", "scopes": ["libraries:read", "query:execute"], "csrf_token": csrf},
        )
    assert response.status_code == 200
    assert b"raw-secret-value" in response.data


@patch("app.presentation.routes.auth_ui.RefreshTokenRepository.find_current_for_application", return_value=None)
@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
def test_register_application_duplicate_name_shows_error(_get_user, _find_token, client):
    csrf = _logged_in(client)
    with (
        patch(
            "app.presentation.routes.auth_ui.ApplicationService.register",
            side_effect=ValidationError("application_name_taken", "An application named 'mcp-server' already exists.", field="name"),
        ),
        patch("app.presentation.routes.auth_ui.ApplicationService.list_applications", return_value=[]),
    ):
        response = client.post(
            "/dashboard/applications",
            data={"name": "mcp-server", "scopes": ["libraries:read"], "csrf_token": csrf},
        )
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_register_application_missing_csrf_rejected(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.list_applications", return_value=[]):
        response = client.post(
            "/dashboard/applications",
            data={"name": "mcp-server", "scopes": ["libraries:read"], "csrf_token": "wrong"},
        )
    assert response.status_code == 400


def test_revoke_token_redirects_to_dashboard(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.revoke_application_token") as revoke:
        response = client.post(f"/dashboard/applications/{uuid4()}/revoke-token", data={"csrf_token": csrf})
    assert response.status_code == 302
    revoke.assert_called_once()


def test_delete_application_redirects_to_dashboard(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(f"/dashboard/applications/{uuid4()}/delete", data={"csrf_token": csrf})
    assert response.status_code == 302
    delete.assert_called_once()


def test_delete_application_missing_csrf_does_not_delete(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(f"/dashboard/applications/{uuid4()}/delete", data={"csrf_token": "wrong"})
    assert response.status_code == 302
    delete.assert_not_called()


@patch("app.presentation.routes.auth_ui.RefreshTokenRepository.find_current_for_application", return_value=None)
@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
def test_dashboard_hides_the_builtin_mcp_application(_get_user, _find_token, client):
    _logged_in(client)
    builtin = _application(id=DEFAULT_MCP_APPLICATION_ID, name="mcp-server (built-in)")
    visible = _application(name="knowledge-store")
    with patch(
        "app.presentation.routes.auth_ui.ApplicationService.list_applications",
        return_value=[builtin, visible],
    ):
        response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"knowledge-store" in response.data
    assert b"mcp-server (built-in)" not in response.data


def test_delete_builtin_mcp_application_is_a_noop(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.delete_application") as delete:
        response = client.post(f"/dashboard/applications/{DEFAULT_MCP_APPLICATION_ID}/delete", data={"csrf_token": csrf})
    assert response.status_code == 302
    delete.assert_not_called()


def test_revoke_token_builtin_mcp_application_is_a_noop(client):
    csrf = _logged_in(client)
    with patch("app.presentation.routes.auth_ui.ApplicationService.revoke_application_token") as revoke:
        response = client.post(
            f"/dashboard/applications/{DEFAULT_MCP_APPLICATION_ID}/revoke-token", data={"csrf_token": csrf}
        )
    assert response.status_code == 302
    revoke.assert_not_called()
