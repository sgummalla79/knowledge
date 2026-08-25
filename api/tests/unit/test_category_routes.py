from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Category
from api.domain.errors import AuthenticationError, ConflictError, NotFoundError

# These tests verify HTTP-layer wiring (status codes, headers, error envelope shape) with
# CategoryService mocked out — real DB behavior (slug uniqueness, description-embedding search)
# is covered by tests/integration/test_category_repository.py against a real Postgres container.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    # Every resource route now requires a real session (require_org_session) rather than a
    # bootstrap default (see docs/DATA_MODEL.md) — seeded once here so route tests can focus on
    # the behavior they're actually testing.
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
        sess["csrf_token"] = "test-csrf-token"
    test_client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
    return test_client


def _category(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        parent_id=None,
        name="test-category",
        slug="test-category",
        description=None,
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Category(**fields)


def test_create_category_returns_201_with_location_header(client):
    category = _category()
    with patch("api.presentation.routes.categories.CategoryService.create_category", return_value=category):
        response = client.post("/categories", json={"name": "test-category"})

    assert response.status_code == 201
    assert response.headers["Location"] == f"/categories/{category.id}"
    assert response.get_json()["name"] == "test-category"


def test_create_category_missing_name_returns_structured_400(client):
    response = client.post("/categories", json={})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field"] == "name"


def test_create_category_duplicate_slug_returns_409(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.create_category",
        side_effect=ConflictError("category_slug_taken", "already exists", field="slug")
    ):
        response = client.post("/categories", json={"name": "dup"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "category_slug_taken"


def test_list_categories_returns_all(client):
    categories = [_category(name="a"), _category(name="b")]
    with patch(
        "api.presentation.routes.categories.CategoryService.list_categories",
        return_value=categories
    ):
        response = client.get("/categories")

    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_get_missing_category_returns_structured_404(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.get_category",
        side_effect=NotFoundError("category_not_found", "Category not found.")
    ):
        response = client.get(f"/categories/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "category_not_found"


def test_update_category_returns_updated_category(client):
    category = _category(name="renamed", description="new description")
    with patch("api.presentation.routes.categories.CategoryService.update_category", return_value=category):
        response = client.patch(
            f"/categories/{category.id}",
            json={"name": "renamed", "description": "new description"}
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "renamed"
    assert body["description"] == "new description"


def test_update_category_missing_name_returns_structured_400(client):
    response = client.patch(
        f"/categories/{uuid4()}", json={"description": "no name"}
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field"] == "name"


def test_update_missing_category_returns_structured_404(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.update_category",
        side_effect=NotFoundError("category_not_found", "Category not found.")
    ):
        response = client.patch(
            f"/categories/{uuid4()}", json={"name": "renamed"}
        )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "category_not_found"


def test_delete_category_returns_documents_deleted_count(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.delete_category", return_value=0
    ) as mock_delete:
        response = client.delete(f"/categories/{uuid4()}")

    assert response.status_code == 200
    assert response.get_json()["documents_deleted"] == 0
    # Default body (no JSON sent at all) must still resolve to a plain, non-cascade delete.
    assert mock_delete.call_args.kwargs["cascade"] is False
    assert mock_delete.call_args.kwargs["current_password"] is None


def test_delete_category_passes_cascade_and_password_through(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.delete_category", return_value=7
    ) as mock_delete:
        response = client.delete(
            f"/categories/{uuid4()}", json={"cascade": True, "current_password": "hunter2"}
        )

    assert response.status_code == 200
    assert response.get_json()["documents_deleted"] == 7
    assert mock_delete.call_args.kwargs["cascade"] is True
    assert mock_delete.call_args.kwargs["current_password"] == "hunter2"


def test_delete_category_cascade_wrong_password_returns_structured_401(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.delete_category",
        side_effect=AuthenticationError("Incorrect password.", code="incorrect_password"),
    ):
        response = client.delete(
            f"/categories/{uuid4()}", json={"cascade": True, "current_password": "wrong"}
        )

    assert response.status_code == 401
    body = response.get_json()
    assert body["error"]["message"] == "Incorrect password."
    # The webui client (client.ts) keys off this exact code to avoid forcing a sign-out/redirect
    # on a simple wrong-password retry -- see that file's own note.
    assert body["error"]["code"] == "incorrect_password"


def test_delete_missing_category_returns_structured_404(client):
    with patch(
        "api.presentation.routes.categories.CategoryService.delete_category",
        side_effect=NotFoundError("category_not_found", "Category not found.")
    ):
        response = client.delete(f"/categories/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "category_not_found"
