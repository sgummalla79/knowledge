import io
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Chunk, Document
from api.domain.errors import NotFoundError, ValidationError

# HTTP-layer wiring only (status codes, headers, error envelope) — DocumentService is mocked.
# Real ingestion/DB behavior is covered by tests/integration/test_ingestion_service.py.


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
    return test_client


def _document(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        source_id=None,
        category_id=None,
        owner_id=uuid4(),
        title="notes.md",
        type="article",
        file_type="md",
        content_uri=None,
        description=None,
        status="indexed",
        error_message=None,
        size_bytes=1024,
        chunk_count=3,
        split_group_id=None,
        split_part=None,
        split_total=None,
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
        indexed_at=now
    )
    fields.update(overrides)
    return Document(**fields)


def test_upload_without_file_returns_structured_400(client):
    response = client.post("/documents")
    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "file"


def test_upload_returns_202_with_job_id(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.start_ingestion",
        return_value="job-123"
    ):
        response = client.post(
            "/documents",
            data={"file": (io.BytesIO(b"hello"), "notes.md")},
            content_type="multipart/form-data"
        )
    assert response.status_code == 202
    assert response.get_json()["job_id"] == "job-123"


def test_list_documents_sets_total_count_header(client):
    documents = [_document(), _document()]
    with patch(
        "api.presentation.routes.documents.DocumentService.list_documents",
        return_value=(documents, 2)
    ):
        response = client.get("/documents")

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    body = response.get_json()
    assert len(body) == 2
    assert body[0]["size_bytes"] == 1024
    assert body[0]["chunk_count"] == 3


def test_list_documents_passes_category_and_shelf_filters_through(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.list_documents",
        return_value=([], 0)
    ) as mock_list:
        category_id = uuid4()
        shelf_id = uuid4()
        response = client.get(f"/documents?category_id={category_id}&shelf_id={shelf_id}")

    assert response.status_code == 200
    assert mock_list.call_args.kwargs["category_id"] == category_id
    assert mock_list.call_args.kwargs["shelf_id"] == shelf_id


def test_list_documents_passes_type_filter_through(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.list_documents",
        return_value=([], 0)
    ) as mock_list:
        response = client.get("/documents?type=dataset")

    assert response.status_code == 200
    assert mock_list.call_args.kwargs["document_type"] == "dataset"


def test_get_document_returns_document(client):
    document = _document()
    with (
        patch("api.presentation.routes.documents.DocumentService.get_document", return_value=document),
        patch(
            "api.presentation.routes.documents.QueryRepository.retrieval_stats_for_document",
            return_value=(0, None)
        ),
    ):
        response = client.get(f"/documents/{document.id}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == str(document.id)
    assert body["type"] == "article"


def test_get_document_includes_retrieval_stats(client):
    document = _document()
    with (
        patch("api.presentation.routes.documents.DocumentService.get_document", return_value=document),
        patch(
            "api.presentation.routes.documents.QueryRepository.retrieval_stats_for_document",
            return_value=(12, 0.87)
        ),
    ):
        response = client.get(f"/documents/{document.id}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["retrieval_count"] == 12
    assert body["avg_similarity"] == 0.87


def test_get_document_missing_returns_structured_404(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.get_document",
        side_effect=NotFoundError("document_not_found", "Document not found.")
    ):
        response = client.get(f"/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_list_document_chunks_returns_chunks(client):
    now = datetime.now(timezone.utc)
    chunks = [
        Chunk(id=uuid4(), document_id=uuid4(), ordinal=0, content="hello", token_count=2, created_at=now)
    ]
    with patch(
        "api.presentation.routes.documents.DocumentService.list_chunks",
        return_value=chunks
    ):
        response = client.get(f"/documents/{uuid4()}/chunks")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["content"] == "hello"


def test_list_document_chunks_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.list_chunks",
        side_effect=NotFoundError("document_not_found", "Document not found.")
    ):
        response = client.get(f"/documents/{uuid4()}/chunks")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_get_job_status_returns_structured_404_when_missing(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.get_job_status",
        side_effect=NotFoundError("job_not_found", "Job not found.")
    ):
        response = client.get("/jobs/missing-job")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "job_not_found"


def test_get_job_status_returns_status_body(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.get_job_status",
        return_value={"status": "indexed", "error": None, "document_id": str(uuid4())}
    ):
        response = client.get("/jobs/job-123")

    assert response.status_code == 200
    assert response.get_json()["status"] == "indexed"


def test_delete_document_returns_204(client):
    with patch("api.presentation.routes.documents.DocumentService.delete_document", return_value=None):
        response = client.delete(f"/documents/{uuid4()}")

    assert response.status_code == 204
    assert response.data == b""


def test_delete_document_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.delete_document",
        side_effect=NotFoundError("document_not_found", "Document not found.")
    ):
        response = client.delete(f"/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_retry_document_returns_202_with_job_id(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.start_retry",
        return_value="retry-job-123"
    ):
        response = client.post(f"/documents/{uuid4()}/retry")

    assert response.status_code == 202
    assert response.get_json()["job_id"] == "retry-job-123"


def test_retry_document_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.start_retry",
        side_effect=NotFoundError("document_not_found", "Document not found.")
    ):
        response = client.post(f"/documents/{uuid4()}/retry")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_retry_document_not_failed_returns_structured_400(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.start_retry",
        side_effect=ValidationError(
            "document_not_retryable", "Only failed documents can be retried.", field="document_id"
        )
    ):
        response = client.post(f"/documents/{uuid4()}/retry")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "document_not_retryable"


def test_crawl_without_url_returns_structured_400(client):
    response = client.post("/documents/crawl", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "url"


def test_crawl_returns_202_with_job_id(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.start_crawl",
        return_value="crawl-job-123"
    ) as mock_start_crawl:
        response = client.post(
            "/documents/crawl",
            json={"url": "https://example.com/docs/intro.htm", "max_pages": 10}
        )

    assert response.status_code == 202
    assert response.get_json()["job_id"] == "crawl-job-123"
    args = mock_start_crawl.call_args[0]
    assert args[2] == "https://example.com/docs/intro.htm"
    assert args[3] == 10


def test_crawl_defaults_max_pages_to_one(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.start_crawl",
        return_value="crawl-job-123"
    ) as mock_start_crawl:
        client.post(
            "/documents/crawl",
            json={"url": "https://example.com/docs/intro.htm"}
        )

    assert mock_start_crawl.call_args[0][3] == 1


def test_get_crawl_job_status_returns_structured_404_when_missing(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.get_crawl_job_status",
        side_effect=NotFoundError("crawl_job_not_found", "Crawl job not found.")
    ):
        response = client.get("/crawl-jobs/missing-job")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "crawl_job_not_found"


def test_get_crawl_job_status_returns_body(client):
    document_id = str(uuid4())
    with patch(
        "api.presentation.routes.documents.DocumentService.get_crawl_job_status",
        return_value={
            "status": "completed",
            "seed_url": "https://example.com/docs/intro.htm",
            "error": None,
            "pages": {
                "https://example.com/docs/intro.htm": {
                    "status": "completed",
                    "document_id": document_id,
                    "error": None,
                }
            },
        }
    ):
        response = client.get("/crawl-jobs/crawl-job-123")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "completed"
    assert body["pages"]["https://example.com/docs/intro.htm"]["document_id"] == document_id


def test_rename_document_returns_updated_document(client):
    renamed = _document(title="new-name.md")
    with patch(
        "api.presentation.routes.documents.DocumentService.rename_document",
        return_value=renamed
    ) as mock_rename:
        response = client.patch(
            f"/documents/{uuid4()}",
            json={"title": "new-name.md"}
        )

    assert response.status_code == 200
    assert response.get_json()["title"] == "new-name.md"
    assert mock_rename.call_args[0][2] == "new-name.md"


def test_rename_document_blank_name_returns_structured_400(client):
    response = client.patch(
        f"/documents/{uuid4()}",
        json={"title": ""}
    )
    assert response.status_code == 400


def test_rename_document_missing_document_returns_structured_404(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.rename_document",
        side_effect=NotFoundError("document_not_found", "Document not found.")
    ):
        response = client.patch(
            f"/documents/{uuid4()}",
            json={"title": "new-name.md"}
        )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "document_not_found"


def test_cancel_job_returns_202(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.cancel_job", return_value=None
    ) as mock_cancel:
        response = client.post("/jobs/job-123/cancel")

    assert response.status_code == 202
    mock_cancel.assert_called_once_with("job-123")


def test_cancel_job_missing_job_returns_structured_404(client):
    with patch(
        "api.presentation.routes.documents.DocumentService.cancel_job",
        side_effect=NotFoundError("job_not_found", "Job not found.")
    ):
        response = client.post("/jobs/missing-job/cancel")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "job_not_found"
