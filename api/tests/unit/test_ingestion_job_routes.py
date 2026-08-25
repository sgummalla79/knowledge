from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import IngestionJob

# HTTP-layer wiring only — IngestionJobService is mocked.


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


def _job(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        source_id=None,
        document_id=None,
        type="upload",
        status="indexed",
        error_message=None,
        items_processed=1,
        triggered_by=uuid4(),
        created_at=now,
        started_at=now,
        finished_at=now,
    )
    fields.update(overrides)
    return IngestionJob(**fields)


def test_list_ingestion_jobs_returns_all(client):
    jobs = [_job(), _job(type="crawl")]
    with patch(
        "api.presentation.routes.ingestion_jobs.IngestionJobService.list_jobs", return_value=jobs
    ) as mock_list:
        response = client.get("/ingestion-jobs")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 2
    assert body[1]["type"] == "crawl"
    assert mock_list.call_args.args[1] == 100
    assert mock_list.call_args.args[2] == 0


def test_list_ingestion_jobs_includes_payload_filename(client):
    """Regression test: an upload job's source filename must reach the client so it can show
    what was actually uploaded instead of just the generic job type (previously missing from
    IngestionJobResponse entirely, even though the domain entity/DB already had it)."""
    jobs = [_job(payload_filename="quarterly-report.pdf"), _job(type="crawl", payload_filename=None)]
    with patch("api.presentation.routes.ingestion_jobs.IngestionJobService.list_jobs", return_value=jobs):
        response = client.get("/ingestion-jobs")

    body = response.get_json()
    assert body[0]["payload_filename"] == "quarterly-report.pdf"
    assert body[1]["payload_filename"] is None


def test_list_ingestion_jobs_includes_size_bytes_from_linked_document(client):
    document_id = uuid4()
    jobs = [_job(document_id=document_id), _job(type="crawl", document_id=None)]
    with (
        patch("api.presentation.routes.ingestion_jobs.IngestionJobService.list_jobs", return_value=jobs),
        patch(
            "api.presentation.routes.ingestion_jobs.IngestionJobService.document_sizes_by_job",
            return_value={jobs[0].id: 4096},
        ),
    ):
        response = client.get("/ingestion-jobs")

    body = response.get_json()
    assert body[0]["size_bytes"] == 4096
    assert body[1]["size_bytes"] is None


def test_list_ingestion_jobs_passes_limit_offset(client):
    with patch(
        "api.presentation.routes.ingestion_jobs.IngestionJobService.list_jobs", return_value=[]
    ) as mock_list:
        response = client.get("/ingestion-jobs?limit=10&offset=20")

    assert response.status_code == 200
    assert mock_list.call_args.args[1] == 10
    assert mock_list.call_args.args[2] == 20
