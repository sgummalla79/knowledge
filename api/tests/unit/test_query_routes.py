from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import ScoredChunk
from api.domain.errors import ValidationError

# HTTP-layer wiring only — RetrievalService is mocked. Real embedding/similarity-search
# behavior is covered by tests/integration/test_retrieval_service.py.


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


def test_query_missing_body_returns_400(client):
    response = client.post(
        f"/categories/{uuid4()}/query", json={}
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "query"


def test_query_top_k_out_of_bounds_returns_400(client):
    response = client.post(
        f"/categories/{uuid4()}/query",
        json={"query": "hello", "top_k": 1000}
    )
    assert response.status_code == 400


def test_query_no_embedding_provider_configured_returns_400(client):
    with patch(
        "api.presentation.routes.query.RetrievalService.query",
        side_effect=ValidationError("embeddings_not_configured", "Embeddings are not configured.")
    ):
        response = client.post(
            f"/categories/{uuid4()}/query",
            json={"query": "hello"}
        )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embeddings_not_configured"


def test_query_returns_scored_chunks(client):
    chunk = ScoredChunk(id=uuid4(), document_id=uuid4(), ordinal=0, content="hello world", score=0.9)
    with patch("api.presentation.routes.query.RetrievalService.query", return_value=[chunk]) as mock_query:
        category_id = uuid4()
        response = client.post(
            f"/categories/{category_id}/query",
            json={"query": "hello"}
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["chunks"][0]["content"] == "hello world"
    assert body["chunks"][0]["score"] == 0.9
    assert mock_query.call_args.kwargs["category_id"] == category_id


def test_query_records_history(client):
    chunk = ScoredChunk(id=uuid4(), document_id=uuid4(), ordinal=0, content="hello world", score=0.9)
    with (
        patch("api.presentation.routes.query.RetrievalService.query", return_value=[chunk]),
        patch("api.presentation.routes.query.QueryHistoryService.record", return_value=None) as mock_record,
    ):
        client.post(f"/categories/{uuid4()}/query", json={"query": "hello"})

    assert mock_record.call_args.args[2] == "hello"
    assert mock_record.call_args.args[4] == [chunk]
