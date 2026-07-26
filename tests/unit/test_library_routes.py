from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import Library
from app.domain.errors import ConflictError, NotFoundError, ValidationError

# These tests verify HTTP-layer wiring (status codes, headers, error envelope shape) with
# LibraryService mocked out — real DB behavior (cascade delete, sorting, uniqueness) is covered
# by tests/integration/test_library_repository.py against a real Postgres container.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _library(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        name="test-library",
        description=None,
        embedding_provider="voyage",
        embedding_model="voyage-3",
        chunk_size=800,
        chunk_overlap=100,
        document_count=0,
        chunk_count=0,
        last_ingested_at=None,
        created_at=now,
        updated_at=now,
    )
    fields.update(overrides)
    return Library(**fields)


def test_create_library_returns_201_with_location_header(client):
    library = _library()
    with patch("app.presentation.routes.libraries.LibraryService.create_library", return_value=library):
        response = client.post("/libraries", json={"name": "test-library"}, headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 201
    assert response.headers["Location"] == f"/libraries/{library.id}"
    assert response.get_json()["name"] == "test-library"


def test_create_library_missing_name_returns_structured_400(client):
    response = client.post("/libraries", json={}, headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["field"] == "name"


def test_create_library_duplicate_name_returns_409(client):
    with patch(
        "app.presentation.routes.libraries.LibraryService.create_library",
        side_effect=ConflictError("library_name_taken", "already exists", field="name"),
    ):
        response = client.post("/libraries", json={"name": "dup"}, headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "library_name_taken"


def test_create_library_bad_chunking_returns_400(client):
    with patch(
        "app.presentation.routes.libraries.LibraryService.create_library",
        side_effect=ValidationError("validation_error", "bad chunking", field="chunk_overlap"),
    ):
        response = client.post(
            "/libraries",
            json={"name": "x", "chunk_size": 10, "chunk_overlap": 20},
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "chunk_overlap"


def test_list_libraries_sets_total_count_header(client):
    libraries = [_library(name="a"), _library(name="b")]
    with patch(
        "app.presentation.routes.libraries.LibraryService.list_libraries",
        return_value=(libraries, 2),
    ):
        response = client.get("/libraries", headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert len(response.get_json()) == 2


def test_get_missing_library_returns_structured_404(client):
    with patch(
        "app.presentation.routes.libraries.LibraryService.get_library",
        side_effect=NotFoundError("library_not_found", "Library not found."),
    ):
        response = client.get(f"/libraries/{uuid4()}", headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "library_not_found"


def test_delete_library_returns_204(client):
    with patch("app.presentation.routes.libraries.LibraryService.delete_library", return_value=None):
        response = client.delete(f"/libraries/{uuid4()}", headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 204


def test_missing_api_key_returns_401(client):
    response = client.get("/libraries")
    assert response.status_code == 401
