from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import ScoredChunk
from app.domain.errors import NotFoundError

# HTTP-layer wiring only — RetrievalService is mocked. Real embedding/similarity-search
# behavior is covered by tests/integration/test_retrieval_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_query_missing_body_returns_400(client):
    response = client.post(
        f"/libraries/{uuid4()}/query", json={}, headers={"X-API-Key": "test-api-key"}
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "query"


def test_query_top_k_out_of_bounds_returns_400(client):
    response = client.post(
        f"/libraries/{uuid4()}/query",
        json={"query": "hello", "top_k": 1000},
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 400


def test_query_missing_library_returns_404(client):
    with patch(
        "app.presentation.routes.query.RetrievalService.query",
        side_effect=NotFoundError("library_not_found", "Library not found."),
    ):
        response = client.post(
            f"/libraries/{uuid4()}/query",
            json={"query": "hello"},
            headers={"X-API-Key": "test-api-key"},
        )
    assert response.status_code == 404


def test_query_returns_scored_chunks(client):
    chunk = ScoredChunk(id=uuid4(), document_id=uuid4(), chunk_index=0, content="hello world", distance=0.1)
    with patch("app.presentation.routes.query.RetrievalService.query", return_value=[chunk]):
        response = client.post(
            f"/libraries/{uuid4()}/query",
            json={"query": "hello"},
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["chunks"][0]["content"] == "hello world"
    assert body["chunks"][0]["distance"] == 0.1
