from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import DashboardStats, MostRetrievedDocument

# HTTP-layer wiring only — StatsService is mocked.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
    return test_client


def test_get_dashboard_stats_returns_payload(client):
    stats = DashboardStats(
        document_count=42,
        chunk_count=1200,
        queries_last_30d=88,
        avg_query_latency_ms=184.5,
        most_retrieved_documents=[
            MostRetrievedDocument(document_id=uuid4(), title="Chunking strategies", retrieval_count=12, avg_similarity=0.87)
        ],
    )
    with patch("api.presentation.routes.stats.StatsService.get_dashboard_stats", return_value=stats):
        response = client.get("/stats/dashboard")

    assert response.status_code == 200
    body = response.get_json()
    assert body["document_count"] == 42
    assert body["chunk_count"] == 1200
    assert body["queries_last_30d"] == 88
    assert body["avg_query_latency_ms"] == 184.5
    assert body["most_retrieved_documents"][0]["title"] == "Chunking strategies"
    assert body["most_retrieved_documents"][0]["retrieval_count"] == 12


def test_get_dashboard_stats_handles_no_query_activity(client):
    stats = DashboardStats(
        document_count=0, chunk_count=0, queries_last_30d=0, avg_query_latency_ms=None, most_retrieved_documents=[]
    )
    with patch("api.presentation.routes.stats.StatsService.get_dashboard_stats", return_value=stats):
        response = client.get("/stats/dashboard")

    assert response.status_code == 200
    body = response.get_json()
    assert body["avg_query_latency_ms"] is None
    assert body["most_retrieved_documents"] == []
