from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Application
from api.domain.errors import ConflictError, NotFoundError, ValidationError

# HTTP-layer wiring only (status codes, headers, error envelope) — ApplicationService is mocked;
# real create/rotate/revoke behavior is exercised by api/tests/integration. The global
# _grant_every_permission fixture (unit/conftest.py) means every request here already has every
# permission unless a test overrides it locally to verify a denial.


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


def _application(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="CI integration",
        description=None,
        auth_method="oauth_client_credentials",
        status="active",
        service_identity_id=uuid4(),
        execute_as_identity_id=None,
        mcp_access=False,
        api_access=True,
        created_by=None,
        last_modified_by=None,
        revoked_at=None,
        revoked_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Application(**fields)


def test_create_application_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.post(
            "/applications",
            json={"name": "x", "auth_method": "oauth_client_credentials", "execute_as_identity_id": str(uuid4())},
        )

    assert response.status_code == 403


def test_create_client_credentials_application_returns_201_with_client_secret(client):
    execute_as_identity_id = uuid4()
    application = _application(auth_method="oauth_client_credentials", execute_as_identity_id=execute_as_identity_id)
    with patch(
        "api.presentation.routes.applications.ApplicationService.create_client_credentials",
        return_value=(application, "raw-client-secret"),
    ):
        response = client.post(
            "/applications",
            json={
                "name": "CI integration",
                "auth_method": "oauth_client_credentials",
                "execute_as_identity_id": str(execute_as_identity_id),
            },
        )

    assert response.status_code == 201
    assert response.headers["Location"] == f"/applications/{application.id}"
    body = response.get_json()
    assert body["client_secret"] == "raw-client-secret"
    assert body["client_id"] == str(application.id)
    assert body["execute_as_identity_id"] == str(execute_as_identity_id)


def test_create_client_credentials_application_requires_execute_as_identity(client):
    response = client.post("/applications", json={"name": "CI integration", "auth_method": "oauth_client_credentials"})

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "execute_as_identity_id"


def test_create_client_credentials_application_rejects_non_member(client):
    with patch(
        "api.presentation.routes.applications.ApplicationService.create_client_credentials",
        side_effect=ValidationError(
            "invalid_execute_as_identity", "This identity is not a member of this organization.", field="execute_as_identity_id"
        ),
    ):
        response = client.post(
            "/applications",
            json={"name": "x", "auth_method": "oauth_client_credentials", "execute_as_identity_id": str(uuid4())},
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_execute_as_identity"


def test_create_authorization_code_application_returns_201(client):
    application = _application(auth_method="oauth_authorization_code")
    with patch(
        "api.presentation.routes.applications.ApplicationService.create_authorization_code_client",
        return_value=application,
    ):
        response = client.post(
            "/applications",
            json={
                "name": "CI integration",
                "auth_method": "oauth_authorization_code",
                "redirect_uris": ["http://127.0.0.1:51000/callback"],
            },
        )

    assert response.status_code == 201
    body = response.get_json()
    assert body["auth_method"] == "oauth_authorization_code"
    assert "client_secret" not in body


def test_create_application_missing_name_returns_structured_400(client):
    response = client.post(
        "/applications",
        json={"auth_method": "oauth_client_credentials", "execute_as_identity_id": str(uuid4())},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "name"


def test_create_application_duplicate_name_returns_409(client):
    with patch(
        "api.presentation.routes.applications.ApplicationService.create_client_credentials",
        side_effect=ConflictError("application_name_taken", "already exists", field="name"),
    ):
        response = client.post(
            "/applications",
            json={"name": "dup", "auth_method": "oauth_client_credentials", "execute_as_identity_id": str(uuid4())},
        )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "application_name_taken"


def test_list_applications_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.get("/applications")

    assert response.status_code == 403


def test_list_applications_returns_all(client):
    application = _application()
    with patch(
        "api.presentation.routes.applications.ApplicationService.list_for_org",
        return_value=[application],
    ):
        response = client.get("/applications")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["id"] == str(application.id)


def test_get_application_not_found_returns_structured_404(client):
    with patch(
        "api.presentation.routes.applications.ApplicationService.get",
        side_effect=NotFoundError("application_not_found", "Connected application not found."),
    ):
        response = client.get(f"/applications/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "application_not_found"


def test_update_application_returns_updated(client):
    application = _application(name="renamed")
    with patch(
        "api.presentation.routes.applications.ApplicationService.update",
        return_value=application,
    ):
        response = client.patch(f"/applications/{application.id}", json={"name": "renamed"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "renamed"


def test_rotate_client_credentials_secret_returns_new_secret(client):
    application = _application(auth_method="oauth_client_credentials", execute_as_identity_id=uuid4())
    with (
        patch("api.presentation.routes.applications.ApplicationService.get", return_value=application),
        patch(
            "api.presentation.routes.applications.ApplicationService.rotate_client_secret",
            return_value=(application, "new-raw-secret"),
        ),
    ):
        response = client.post(f"/applications/{application.id}/rotate-key")

    assert response.status_code == 200
    body = response.get_json()
    assert body["client_secret"] == "new-raw-secret"
    assert body["client_id"] == str(application.id)


def test_rotate_authorization_code_application_has_no_rotatable_secret(client):
    application = _application(auth_method="oauth_authorization_code")
    with patch("api.presentation.routes.applications.ApplicationService.get", return_value=application):
        response = client.post(f"/applications/{application.id}/rotate-key")

    assert response.status_code == 400


def test_revoke_application_returns_revoked_status(client):
    application = _application(status="revoked", revoked_at=datetime.now(timezone.utc))
    with patch(
        "api.presentation.routes.applications.ApplicationService.revoke",
        return_value=application,
    ):
        response = client.post(f"/applications/{application.id}/revoke")

    assert response.status_code == 200
    assert response.get_json()["status"] == "revoked"


def test_delete_application_returns_204(client):
    with patch("api.presentation.routes.applications.ApplicationService.delete", return_value=None):
        response = client.delete(f"/applications/{uuid4()}")

    assert response.status_code == 204
