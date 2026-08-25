from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from api.application.ingestion_job_service import IngestionJobService
from api.domain.entities import IngestionJob


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


def _document(id, size_bytes):
    document = MagicMock()
    document.id = id
    document.size_bytes = size_bytes
    return document


def test_document_sizes_by_job_maps_size_for_jobs_with_a_linked_document():
    document_id = uuid4()
    job = _job(document_id=document_id)
    document_repo = MagicMock()
    document_repo.list_by_ids.return_value = [_document(document_id, 2048)]

    service = IngestionJobService(MagicMock(), document_repo)
    sizes = service.document_sizes_by_job([job])

    assert sizes == {job.id: 2048}
    document_repo.list_by_ids.assert_called_once_with([document_id])


def test_document_sizes_by_job_skips_jobs_with_no_linked_document():
    """A still-queued/processing job, a crawl/reindex job, or a split-PDF job's parts (which use
    document_ids, plural, not document_id) have no single document to look a size up for -- these
    just don't appear in the returned mapping rather than erroring or looking up None."""
    job_without_document = _job(document_id=None)
    document_repo = MagicMock()

    service = IngestionJobService(MagicMock(), document_repo)
    sizes = service.document_sizes_by_job([job_without_document])

    assert sizes == {}
    document_repo.list_by_ids.assert_not_called()


def test_document_sizes_by_job_batches_lookup_across_multiple_jobs():
    document_id_a, document_id_b = uuid4(), uuid4()
    job_a = _job(document_id=document_id_a)
    job_b = _job(document_id=document_id_b)
    job_without_document = _job(document_id=None)
    document_repo = MagicMock()
    document_repo.list_by_ids.return_value = [_document(document_id_a, 100), _document(document_id_b, 200)]

    service = IngestionJobService(MagicMock(), document_repo)
    sizes = service.document_sizes_by_job([job_a, job_b, job_without_document])

    assert sizes == {job_a.id: 100, job_b.id: 200}
    document_repo.list_by_ids.assert_called_once_with([document_id_a, document_id_b])
