from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Shelf
from api.domain.errors import ConflictError, NotFoundError, ValidationError

# HTTP-layer wiring only (status codes, headers, error envelope) — ShelfService is mocked.
# Real DB behavior (slug uniqueness, document/member counts) belongs in an integration suite.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
        sess["csrf_token"] = "test-csrf-token"
    test_client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
    return test_client


def _shelf(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="Engineering",
        slug="engineering",
        description=None,
        is_default=False,
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Shelf(**fields)


def test_create_shelf_returns_201_with_location_header(client):
    shelf = _shelf()
    with patch("api.presentation.routes.shelves.ShelfService.create_shelf", return_value=shelf):
        response = client.post("/shelves", json={"name": "Engineering"})

    assert response.status_code == 201
    assert response.headers["Location"] == f"/shelves/{shelf.id}"
    body = response.get_json()
    assert body["name"] == "Engineering"
    assert body["document_count"] == 0
    assert body["member_count"] == 0


def test_create_shelf_missing_name_returns_structured_400(client):
    response = client.post("/shelves", json={})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field"] == "name"


def test_create_shelf_duplicate_slug_returns_409(client):
    with patch(
        "api.presentation.routes.shelves.ShelfService.create_shelf",
        side_effect=ConflictError("shelf_slug_taken", "already exists", field="slug"),
    ):
        response = client.post("/shelves", json={"name": "dup"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "shelf_slug_taken"


def test_list_shelves_includes_counts(client):
    shelves = [_shelf(name="a"), _shelf(name="b")]
    with (
        patch("api.presentation.routes.shelves.ShelfService.list_shelves", return_value=shelves),
        patch("api.presentation.routes.shelves.ShelfService.document_count", return_value=4),
        patch("api.presentation.routes.shelves.ShelfService.member_count", return_value=2),
    ):
        response = client.get("/shelves")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 2
    assert body[0]["document_count"] == 4
    assert body[0]["member_count"] == 2


def test_get_missing_shelf_returns_structured_404(client):
    with patch(
        "api.presentation.routes.shelves.ShelfService.get_shelf",
        side_effect=NotFoundError("shelf_not_found", "Shelf not found."),
    ):
        response = client.get(f"/shelves/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "shelf_not_found"


def test_update_shelf_returns_updated_shelf(client):
    shelf = _shelf(name="renamed")
    with (
        patch("api.presentation.routes.shelves.ShelfService.update_shelf", return_value=shelf),
        patch("api.presentation.routes.shelves.ShelfService.document_count", return_value=0),
        patch("api.presentation.routes.shelves.ShelfService.member_count", return_value=0),
    ):
        response = client.patch(f"/shelves/{shelf.id}", json={"name": "renamed"})

    assert response.status_code == 200
    assert response.get_json()["name"] == "renamed"


def test_delete_shelf_returns_204(client):
    with patch("api.presentation.routes.shelves.ShelfService.delete_shelf", return_value=None):
        response = client.delete(f"/shelves/{uuid4()}")

    assert response.status_code == 204


def test_delete_default_shelf_returns_structured_400(client):
    with patch(
        "api.presentation.routes.shelves.ShelfService.delete_shelf",
        side_effect=ValidationError("default_shelf_not_deletable", "can't delete", field="shelf_id"),
    ):
        response = client.delete(f"/shelves/{uuid4()}")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "default_shelf_not_deletable"


def test_add_document_to_shelf_returns_204(client):
    with (
        patch("api.presentation.routes.shelves._verify_document_ownership", return_value=None),
        patch("api.presentation.routes.shelves.ShelfService.add_document", return_value=None),
    ):
        response = client.post(f"/shelves/{uuid4()}/documents", json={"document_id": str(uuid4())})

    assert response.status_code == 204


def test_add_document_to_shelf_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.shelves._verify_document_ownership",
        side_effect=NotFoundError("document_not_found", "Document not found."),
    ):
        response = client.post(f"/shelves/{uuid4()}/documents", json={"document_id": str(uuid4())})

    assert response.status_code == 404


def test_remove_document_from_shelf_returns_204(client):
    with (
        patch("api.presentation.routes.shelves._verify_document_ownership", return_value=None),
        patch("api.presentation.routes.shelves.ShelfService.remove_document", return_value=None),
    ):
        response = client.delete(f"/shelves/{uuid4()}/documents/{uuid4()}")

    assert response.status_code == 204


def test_list_document_shelves_returns_shelves(client):
    shelf = _shelf()
    with (
        patch("api.presentation.routes.shelves._verify_document_ownership", return_value=None),
        patch("api.presentation.routes.shelves.ShelfService.list_document_shelves", return_value=[shelf]),
        patch("api.presentation.routes.shelves.ShelfService.document_count", return_value=1),
        patch("api.presentation.routes.shelves.ShelfService.member_count", return_value=1),
    ):
        response = client.get(f"/documents/{uuid4()}/shelves")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["id"] == str(shelf.id)


def test_list_document_shelves_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.shelves._verify_document_ownership",
        side_effect=NotFoundError("document_not_found", "Document not found."),
    ):
        response = client.get(f"/documents/{uuid4()}/shelves")

    assert response.status_code == 404


def test_grant_shelf_access_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.post(f"/shelves/{uuid4()}/access", json={"user_id": str(uuid4())})

    assert response.status_code == 403


def test_grant_shelf_access_returns_204(client):
    with patch("api.presentation.routes.shelves.ShelfService.grant_access", return_value=None):
        response = client.post(f"/shelves/{uuid4()}/access", json={"user_id": str(uuid4())})

    assert response.status_code == 204


def test_revoke_shelf_access_returns_204(client):
    with patch("api.presentation.routes.shelves.ShelfService.revoke_access", return_value=None):
        response = client.delete(f"/shelves/{uuid4()}/access/{uuid4()}")

    assert response.status_code == 204
