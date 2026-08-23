from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import SessionSettings

# HTTP-layer only — SessionSettingsService is mocked. Real DB behavior (default-when-no-row,
# upsert) is covered by tests/integration/test_session_settings_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    test_client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
    return test_client


def _settings(**overrides):
    fields = dict(
        org_id=uuid4(),
        inactivity_timeout_minutes=120,
        last_modified_by=None,
        last_modified_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return SessionSettings(**fields)


def test_get_session_settings_returns_default_when_none_configured(client):
    with patch(
        "api.presentation.routes.session_settings.SessionSettingsService.get", return_value=_settings()
    ):
        response = client.get("/session-settings")

    assert response.status_code == 200
    assert response.get_json()["inactivity_timeout_minutes"] == 120


def test_get_session_settings_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.get("/session-settings")

    assert response.status_code == 403


def test_update_session_settings_returns_updated_value(client):
    with patch(
        "api.presentation.routes.session_settings.SessionSettingsService.update",
        return_value=_settings(inactivity_timeout_minutes=15),
    ) as mock_update:
        response = client.put("/session-settings", json={"inactivity_timeout_minutes": 15})

    assert response.status_code == 200
    assert response.get_json()["inactivity_timeout_minutes"] == 15
    mock_update.assert_called_once()


def test_update_session_settings_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.put("/session-settings", json={"inactivity_timeout_minutes": 15})

    assert response.status_code == 403


def test_update_session_settings_below_minimum_returns_structured_400(client):
    response = client.put("/session-settings", json={"inactivity_timeout_minutes": 10})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_update_session_settings_above_maximum_returns_structured_400(client):
    response = client.put("/session-settings", json={"inactivity_timeout_minutes": 1500})

    assert response.status_code == 400


def test_update_session_settings_rejects_unknown_field(client):
    response = client.put("/session-settings", json={"inactivity_timeout_minutes": 60, "extra_field": "x"})

    assert response.status_code == 400
