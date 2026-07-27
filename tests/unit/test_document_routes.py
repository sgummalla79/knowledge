import io
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import Document
from app.domain.errors import NotFoundError

# HTTP-layer wiring only (status codes, headers, error envelope) — DocumentService is mocked.
# Real ingestion/DB behavior is covered by tests/integration/test_ingestion_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _document(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        library_id=uuid4(),
        source_filename="notes.md",
        file_type="md",
        status="completed",
        ingested_at=now,
        created_at=now,
    )
    fields.update(overrides)
    return Document(**fields)


def test_upload_without_file_returns_structured_400(client, auth_headers):
    response = client.post(f"/libraries/{uuid4()}/documents", headers=auth_headers("documents:write"))
    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "file"


def test_upload_missing_library_returns_404(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.start_ingestion",
        side_effect=NotFoundError("library_not_found", "Library not found."),
    ):
        response = client.post(
            f"/libraries/{uuid4()}/documents",
            data={"file": (io.BytesIO(b"hello"), "notes.md")},
            content_type="multipart/form-data",
            headers=auth_headers("documents:write"),
        )
    assert response.status_code == 404


def test_upload_returns_202_with_job_id(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.start_ingestion",
        return_value="job-123",
    ):
        response = client.post(
            f"/libraries/{uuid4()}/documents",
            data={"file": (io.BytesIO(b"hello"), "notes.md")},
            content_type="multipart/form-data",
            headers=auth_headers("documents:write"),
        )
    assert response.status_code == 202
    assert response.get_json()["job_id"] == "job-123"


def test_list_documents_sets_total_count_header(client, auth_headers):
    documents = [_document(), _document()]
    with patch(
        "app.presentation.routes.documents.DocumentService.list_documents",
        return_value=(documents, 2),
    ):
        response = client.get(f"/libraries/{uuid4()}/documents", headers=auth_headers("documents:read"))

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert len(response.get_json()) == 2


def test_get_job_status_returns_structured_404_when_missing(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.get_job_status",
        side_effect=NotFoundError("job_not_found", "Job not found."),
    ):
        response = client.get(f"/libraries/{uuid4()}/jobs/missing-job", headers=auth_headers("documents:read"))

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "job_not_found"


def test_get_job_status_returns_status_body(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.get_job_status",
        return_value={"status": "completed", "error": None, "document_id": str(uuid4())},
    ):
        response = client.get(f"/libraries/{uuid4()}/jobs/job-123", headers=auth_headers("documents:read"))

    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"
