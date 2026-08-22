from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Query

# HTTP-layer wiring only — QueryHistoryService is mocked.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
    return test_client


def _query(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        user_id=uuid4(),
        query_text="vector databases",
        latency_ms=42,
        result_count=5,
        created_at=now,
    )
    fields.update(overrides)
    return Query(**fields)


def test_list_queries_returns_all(client):
    history = [_query(), _query(query_text="chunking strategies")]
    with patch(
        "api.presentation.routes.queries.QueryHistoryService.list_history", return_value=history
    ) as mock_list:
        response = client.get("/queries")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 2
    assert body[1]["query_text"] == "chunking strategies"
    assert mock_list.call_args.args[1] == 100
    assert mock_list.call_args.args[2] == 0


def test_list_queries_passes_limit_offset(client):
    with patch(
        "api.presentation.routes.queries.QueryHistoryService.list_history", return_value=[]
    ) as mock_list:
        response = client.get("/queries?limit=10&offset=20")

    assert response.status_code == 200
    assert mock_list.call_args.args[1] == 10
    assert mock_list.call_args.args[2] == 20
