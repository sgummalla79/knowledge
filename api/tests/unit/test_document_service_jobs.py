from uuid import uuid4

import pytest

from api.application.crawl_job_store import CrawlJobStore
from api.application.document_service import DocumentService
from api.application.job_store import JobStore
from api.domain.errors import NotFoundError

# Regression tests for a real IDOR found in a security review (see this repo's Phase A history):
# ingestion/crawl job status endpoints had zero org_id scoping — any org could poll or cancel any
# other org's job if the (unguessable but leakable, e.g. via logs) job_id was known. No DB needed
# here — JobStore/CrawlJobStore are in-memory, and document_repo/chunk_repo are never touched by
# any of the three methods under test.


@pytest.fixture()
def service():
    return DocumentService(document_repo=None, chunk_repo=None)


def test_get_job_status_rejects_a_different_org(service):
    owner_org = uuid4()
    other_org = uuid4()
    job_id = JobStore.create(owner_org)

    assert service.get_job_status(owner_org, job_id)["status"] == "pending"
    with pytest.raises(NotFoundError):
        service.get_job_status(other_org, job_id)


def test_cancel_job_rejects_a_different_org(service):
    owner_org = uuid4()
    other_org = uuid4()
    job_id = JobStore.create(owner_org)

    with pytest.raises(NotFoundError):
        service.cancel_job(other_org, job_id)
    assert JobStore.is_cancellation_requested(job_id) is False

    service.cancel_job(owner_org, job_id)
    assert JobStore.is_cancellation_requested(job_id) is True


def test_get_crawl_job_status_rejects_a_different_org(service):
    owner_org = uuid4()
    other_org = uuid4()
    job_id = CrawlJobStore.create(owner_org, "https://example.com")

    assert service.get_crawl_job_status(owner_org, job_id)["status"] == "pending"
    with pytest.raises(NotFoundError):
        service.get_crawl_job_status(other_org, job_id)
