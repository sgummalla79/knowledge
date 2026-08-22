from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Tag
from api.domain.errors import ConflictError, NotFoundError

# HTTP-layer wiring only (status codes, headers, error envelope) — TagService is mocked.


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


def _tag(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(id=uuid4(), org_id=uuid4(), name="billing", created_by=None, created_at=now)
    fields.update(overrides)
    return Tag(**fields)


def test_create_tag_returns_201_with_location_header(client):
    tag = _tag()
    with patch("api.presentation.routes.tags.TagService.create_tag", return_value=tag):
        response = client.post("/tags", json={"name": "billing"})

    assert response.status_code == 201
    assert response.headers["Location"] == f"/tags/{tag.id}"
    assert response.get_json()["name"] == "billing"


def test_create_tag_missing_name_returns_structured_400(client):
    response = client.post("/tags", json={})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field"] == "name"


def test_create_tag_duplicate_name_returns_409(client):
    with patch(
        "api.presentation.routes.tags.TagService.create_tag",
        side_effect=ConflictError("tag_name_taken", "already exists", field="name"),
    ):
        response = client.post("/tags", json={"name": "dup"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "tag_name_taken"


def test_list_tags_returns_all(client):
    tags = [_tag(name="a"), _tag(name="b")]
    with patch("api.presentation.routes.tags.TagService.list_tags", return_value=tags):
        response = client.get("/tags")

    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_tag_document_returns_204(client):
    with (
        patch("api.presentation.routes.tags._verify_document_ownership", return_value=None),
        patch("api.presentation.routes.tags.TagService.tag_document", return_value=None),
    ):
        response = client.post(f"/documents/{uuid4()}/tags", json={"tag_id": str(uuid4())})

    assert response.status_code == 204


def test_tag_document_missing_tag_returns_structured_404(client):
    with (
        patch("api.presentation.routes.tags._verify_document_ownership", return_value=None),
        patch(
            "api.presentation.routes.tags.TagService.tag_document",
            side_effect=NotFoundError("tag_not_found", "Tag not found."),
        ),
    ):
        response = client.post(f"/documents/{uuid4()}/tags", json={"tag_id": str(uuid4())})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "tag_not_found"


def test_tag_document_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.tags._verify_document_ownership",
        side_effect=NotFoundError("document_not_found", "Document not found."),
    ):
        response = client.post(f"/documents/{uuid4()}/tags", json={"tag_id": str(uuid4())})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_untag_document_returns_204(client):
    with (
        patch("api.presentation.routes.tags._verify_document_ownership", return_value=None),
        patch("api.presentation.routes.tags.TagService.untag_document", return_value=None),
    ):
        response = client.delete(f"/documents/{uuid4()}/tags/{uuid4()}")

    assert response.status_code == 204


def test_list_document_tags_returns_all(client):
    tags = [_tag(name="a")]
    with (
        patch("api.presentation.routes.tags._verify_document_ownership", return_value=None),
        patch("api.presentation.routes.tags.TagService.list_document_tags", return_value=tags),
    ):
        response = client.get(f"/documents/{uuid4()}/tags")

    assert response.status_code == 200
    assert len(response.get_json()) == 1
