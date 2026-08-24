from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.application.document_service import DocumentService
from api.domain.entities import IngestionJob
from api.domain.errors import NotFoundError

# Regression tests for a real IDOR found in a security review (see this repo's Phase A history):
# ingestion/crawl job status endpoints had zero org_id scoping — any org could poll or cancel any
# other org's job if the (unguessable but leakable, e.g. via logs) job_id was known. A mocked
# IngestionJobRepository is enough here — the fix under test is DocumentService's own org_id
# comparison, not anything the real repository/DB needs to prove.


def _job(org_id, job_type="upload", **overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=org_id,
        source_id=None,
        document_id=None,
        type=job_type,
        status="queued",
        error_message=None,
        items_processed=0,
        triggered_by=uuid4(),
        created_at=now,
        started_at=None,
        finished_at=None,
    )
    fields.update(overrides)
    return IngestionJob(**fields)


def _service_with(ingestion_jobs):
    return DocumentService(document_repo=None, chunk_repo=None, ingestion_job_repo=ingestion_jobs)


def test_get_job_status_rejects_a_different_org():
    owner_org, other_org = uuid4(), uuid4()
    job = _job(owner_org)
    ingestion_jobs = MagicMock()
    ingestion_jobs.get.return_value = job

    service = _service_with(ingestion_jobs)
    assert service.get_job_status(owner_org, str(job.id))["status"] == "pending"
    with pytest.raises(NotFoundError):
        service.get_job_status(other_org, str(job.id))


def test_get_job_status_rejects_a_crawl_job_id():
    org_id = uuid4()
    job = _job(org_id, job_type="crawl")
    ingestion_jobs = MagicMock()
    ingestion_jobs.get.return_value = job

    with pytest.raises(NotFoundError):
        _service_with(ingestion_jobs).get_job_status(org_id, str(job.id))


def test_cancel_job_rejects_a_different_org():
    owner_org, other_org = uuid4(), uuid4()
    job = _job(owner_org)
    ingestion_jobs = MagicMock()
    ingestion_jobs.get.return_value = job

    service = _service_with(ingestion_jobs)
    with pytest.raises(NotFoundError):
        service.cancel_job(other_org, str(job.id))
    ingestion_jobs.request_cancellation.assert_not_called()

    service.cancel_job(owner_org, str(job.id))
    ingestion_jobs.request_cancellation.assert_called_once_with(job.id)


def test_get_job_status_missing_job_raises_job_not_found():
    ingestion_jobs = MagicMock()
    ingestion_jobs.get.return_value = None
    with pytest.raises(NotFoundError):
        _service_with(ingestion_jobs).get_job_status(uuid4(), str(uuid4()))


def test_get_job_status_malformed_job_id_raises_job_not_found():
    ingestion_jobs = MagicMock()
    with pytest.raises(NotFoundError):
        _service_with(ingestion_jobs).get_job_status(uuid4(), "does-not-exist")
    ingestion_jobs.get.assert_not_called()


def test_get_crawl_job_status_rejects_a_different_org():
    owner_org, other_org = uuid4(), uuid4()
    job = _job(owner_org, job_type="crawl", crawl_url="https://example.com")
    ingestion_jobs = MagicMock()
    ingestion_jobs.get.return_value = job

    service = _service_with(ingestion_jobs)
    assert service.get_crawl_job_status(owner_org, str(job.id))["status"] == "pending"
    with pytest.raises(NotFoundError):
        service.get_crawl_job_status(other_org, str(job.id))


def test_get_crawl_job_status_rejects_an_upload_job_id():
    org_id = uuid4()
    job = _job(org_id, job_type="upload")
    ingestion_jobs = MagicMock()
    ingestion_jobs.get.return_value = job

    with pytest.raises(NotFoundError):
        _service_with(ingestion_jobs).get_crawl_job_status(org_id, str(job.id))
