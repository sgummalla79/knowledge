import io
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import Document
from app.domain.errors import NotFoundError, ValidationError

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
        error_message=None,
        size_bytes=1024,
        chunk_count=3,
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
    body = response.get_json()
    assert len(body) == 2
    assert body[0]["size_bytes"] == 1024
    assert body[0]["chunk_count"] == 3


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


def test_delete_document_returns_204(client, auth_headers):
    with patch("app.presentation.routes.documents.DocumentService.delete_document", return_value=None):
        response = client.delete(
            f"/libraries/{uuid4()}/documents/{uuid4()}", headers=auth_headers("documents:write")
        )

    assert response.status_code == 204
    assert response.data == b""


def test_delete_document_missing_library_returns_structured_404(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.delete_document",
        side_effect=NotFoundError("library_not_found", "Library not found."),
    ):
        response = client.delete(
            f"/libraries/{uuid4()}/documents/{uuid4()}", headers=auth_headers("documents:write")
        )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "library_not_found"


def test_delete_document_missing_document_returns_structured_404(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.delete_document",
        side_effect=NotFoundError("document_not_found", "Document not found."),
    ):
        response = client.delete(
            f"/libraries/{uuid4()}/documents/{uuid4()}", headers=auth_headers("documents:write")
        )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_delete_document_requires_write_scope(client, auth_headers):
    response = client.delete(
        f"/libraries/{uuid4()}/documents/{uuid4()}", headers=auth_headers("documents:read")
    )

    assert response.status_code == 403


def test_retry_document_returns_202_with_job_id(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.start_retry",
        return_value="retry-job-123",
    ):
        response = client.post(
            f"/libraries/{uuid4()}/documents/{uuid4()}/retry", headers=auth_headers("documents:write")
        )

    assert response.status_code == 202
    assert response.get_json()["job_id"] == "retry-job-123"


def test_retry_document_missing_library_returns_structured_404(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.start_retry",
        side_effect=NotFoundError("library_not_found", "Library not found."),
    ):
        response = client.post(
            f"/libraries/{uuid4()}/documents/{uuid4()}/retry", headers=auth_headers("documents:write")
        )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "library_not_found"


def test_retry_document_missing_document_returns_structured_404(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.start_retry",
        side_effect=NotFoundError("document_not_found", "Document not found."),
    ):
        response = client.post(
            f"/libraries/{uuid4()}/documents/{uuid4()}/retry", headers=auth_headers("documents:write")
        )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_retry_document_not_failed_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.documents.DocumentService.start_retry",
        side_effect=ValidationError(
            "document_not_retryable", "Only failed documents can be retried.", field="document_id"
        ),
    ):
        response = client.post(
            f"/libraries/{uuid4()}/documents/{uuid4()}/retry", headers=auth_headers("documents:write")
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "document_not_retryable"


def test_retry_document_requires_write_scope(client, auth_headers):
    response = client.post(
        f"/libraries/{uuid4()}/documents/{uuid4()}/retry", headers=auth_headers("documents:read")
    )

    assert response.status_code == 403
