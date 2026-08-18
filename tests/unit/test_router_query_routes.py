from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain import error_codes
from app.domain.entities import RoutedScoredChunk, ScoredChunk
from app.domain.errors import ValidationError

# HTTP-layer wiring only — CategoryRouterService is mocked. Real routing/merge behavior is covered
# by tests/unit/test_category_router_service_unit.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_query_missing_body_returns_400(client):
    response = client.post("/query", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "query"


def test_query_top_k_out_of_bounds_returns_400(client):
    response = client.post(
        "/query", json={"query": "hello", "top_k": 1000}
    )
    assert response.status_code == 400


def test_query_no_provider_configured_returns_error(client):
    with patch(
        "app.presentation.routes.router_query.CategoryRouterService.query",
        side_effect=ValidationError(error_codes.EMBEDDINGS_NOT_CONFIGURED, "Embeddings are not configured.")
    ):
        response = client.post("/query", json={"query": "hello"})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == error_codes.EMBEDDINGS_NOT_CONFIGURED


def test_query_no_category_clears_threshold_returns_empty_list(client):
    with patch("app.presentation.routes.router_query.CategoryRouterService.query", return_value=[]):
        response = client.post("/query", json={"query": "hello"})
    assert response.status_code == 200
    assert response.get_json()["chunks"] == []


def test_query_returns_routed_scored_chunks(client):
    category_id = uuid4()
    chunk = ScoredChunk(id=uuid4(), document_id=uuid4(), ordinal=0, content="hello world", score=0.9)
    routed = RoutedScoredChunk(category_id=category_id, category_name="docs", chunk=chunk)
    with patch("app.presentation.routes.router_query.CategoryRouterService.query", return_value=[routed]):
        response = client.post("/query", json={"query": "hello"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["chunks"][0]["content"] == "hello world"
    assert body["chunks"][0]["score"] == 0.9
    assert body["chunks"][0]["category_id"] == str(category_id)
    assert body["chunks"][0]["category_name"] == "docs"


