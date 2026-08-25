from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from api.application.pdf_split_ingestion_service import PdfSplitIngestionService
from api.domain.errors import IngestionCancelled, ValidationError
from api.infrastructure.parsing.pdf_splitter import SplitPlan

_SOURCE_PATH = "org/job/upload.bin"


def _plan(total_parts: int) -> SplitPlan:
    return SplitPlan(total_parts=total_parts, pages_per_part=1, overlap_pages=0)


def _ids():
    return uuid4(), uuid4(), uuid4()  # org_id, owner_id, job_id


def _settings():
    settings = MagicMock()
    settings.chunk_size = 800
    settings.chunk_overlap = 100
    return settings


def _storage(size_bytes: int = 100):
    storage = MagicMock()
    storage.size.return_value = size_bytes
    storage.resolve.return_value = _SOURCE_PATH
    storage.path_for_part.side_effect = lambda org_id, job_id, index: f"org/job/parts/part-{index}.bin"
    return storage


def test_non_pdf_within_limit_delegates_straight_to_ingest():
    ingestion_service = MagicMock()
    ingestion_service.ingest.return_value = MagicMock(id=uuid4())
    splitter = MagicMock()
    storage = _storage(size_bytes=11)

    service = PdfSplitIngestionService(ingestion_service, storage, splitter)
    org_id, owner_id, job_id = _ids()
    results = []
    service.ingest(
        org_id, owner_id, job_id, "notes.md", _SOURCE_PATH, on_part_result=lambda *a: results.append(a)
    )

    splitter.plan_for.assert_not_called()
    ingestion_service.ingest.assert_called_once()
    assert ingestion_service.ingest.call_args.kwargs.get("file_type") is None
    assert len(results) == 1
    assert results[0][0:2] == (1, 1)
    assert results[0][3] is None


def test_non_pdf_over_limit_raises_file_too_large():
    ingestion_service = MagicMock()
    splitter = MagicMock()
    storage = _storage(size_bytes=51 * 1024 * 1024)
    service = PdfSplitIngestionService(ingestion_service, storage, splitter)

    org_id, owner_id, job_id = _ids()
    with pytest.raises(ValidationError):
        service.ingest(org_id, owner_id, job_id, "huge.md", _SOURCE_PATH)
    ingestion_service.ingest.assert_not_called()


def test_pdf_below_split_threshold_delegates_as_single_document():
    ingestion_service = MagicMock()
    ingestion_service.require_embedding_settings.return_value = _settings()
    ingestion_service.ingest.return_value = MagicMock(id=uuid4())
    splitter = MagicMock()
    splitter.plan_for.return_value = None  # no real split needed
    storage = _storage()

    service = PdfSplitIngestionService(ingestion_service, storage, splitter)
    org_id, owner_id, job_id = _ids()
    results = []
    service.ingest(
        org_id, owner_id, job_id, "small.pdf", _SOURCE_PATH, on_part_result=lambda *a: results.append(a)
    )

    ingestion_service.ingest.assert_called_once()
    call_kwargs = ingestion_service.ingest.call_args.kwargs
    assert call_kwargs["file_type"] == "pdf"
    assert call_kwargs.get("split_group_id") is None
    assert results[0][0:2] == (1, 1)
    splitter.iter_parts.assert_not_called()


def test_pdf_exception_on_single_part_propagates_uncaught():
    # Single-document path (below threshold) must keep today's exact failure semantics — the
    # exception propagates so DocumentService's outer catch marks the whole job failed, it is
    # NOT swallowed into on_part_result.
    ingestion_service = MagicMock()
    ingestion_service.require_embedding_settings.return_value = _settings()
    ingestion_service.ingest.side_effect = RuntimeError("embedding failed")
    splitter = MagicMock()
    splitter.plan_for.return_value = None
    storage = _storage()

    service = PdfSplitIngestionService(ingestion_service, storage, splitter)
    org_id, owner_id, job_id = _ids()
    with pytest.raises(RuntimeError):
        service.ingest(org_id, owner_id, job_id, "small.pdf", _SOURCE_PATH)


def test_split_pdf_creates_one_document_per_part_with_shared_group_id():
    ingestion_service = MagicMock()
    ingestion_service.require_embedding_settings.return_value = _settings()
    ingestion_service.ingest.side_effect = lambda *a, **kw: MagicMock(id=uuid4())
    splitter = MagicMock()
    splitter.plan_for.return_value = _plan(total_parts=3)
    splitter.iter_parts.return_value = [b"part-1", b"part-2", b"part-3"]
    storage = _storage()

    service = PdfSplitIngestionService(ingestion_service, storage, splitter)
    org_id, owner_id, job_id = _ids()
    results = []
    service.ingest(
        org_id, owner_id, job_id, "big.pdf", _SOURCE_PATH, on_part_result=lambda *a: results.append(a)
    )

    assert ingestion_service.ingest.call_count == 3
    group_ids = set()
    for index, call in enumerate(ingestion_service.ingest.call_args_list, start=1):
        assert call.kwargs["file_type"] == "pdf"
        assert call.kwargs["split_part"] == index
        assert call.kwargs["split_total"] == 3
        assert call.args[2] == f"big.pdf (part {index} of 3)"
        group_ids.add(call.kwargs["split_group_id"])
    assert len(group_ids) == 1  # every part shares the same split_group_id

    assert len(results) == 3
    assert all(err is None for (_, _, _, err) in results)


def test_one_failed_part_does_not_abort_the_remaining_parts():
    ingestion_service = MagicMock()
    ingestion_service.require_embedding_settings.return_value = _settings()

    def ingest(org_id, owner_id, filename, source_path, **kwargs):
        if kwargs.get("split_part") == 2:
            raise RuntimeError("embedding failed")
        return MagicMock(id=uuid4())

    ingestion_service.ingest.side_effect = ingest
    splitter = MagicMock()
    splitter.plan_for.return_value = _plan(total_parts=3)
    splitter.iter_parts.return_value = [b"part-1", b"part-2", b"part-3"]
    storage = _storage()

    service = PdfSplitIngestionService(ingestion_service, storage, splitter)
    org_id, owner_id, job_id = _ids()
    results = []
    service.ingest(
        org_id, owner_id, job_id, "big.pdf", _SOURCE_PATH, on_part_result=lambda *a: results.append(a)
    )

    assert ingestion_service.ingest.call_count == 3
    assert len(results) == 3
    _, _, doc_1, err_1 = results[0]
    _, _, doc_2, err_2 = results[1]
    _, _, doc_3, err_3 = results[2]
    assert doc_1 is not None and err_1 is None
    assert doc_2 is None and isinstance(err_2, RuntimeError)
    assert doc_3 is not None and err_3 is None


def test_cancellation_between_parts_aborts_remaining_parts():
    ingestion_service = MagicMock()
    ingestion_service.require_embedding_settings.return_value = _settings()
    ingestion_service.ingest.side_effect = lambda *a, **kw: MagicMock(id=uuid4())
    splitter = MagicMock()
    splitter.plan_for.return_value = _plan(total_parts=3)
    splitter.iter_parts.return_value = [b"part-1", b"part-2", b"part-3"]
    storage = _storage()

    service = PdfSplitIngestionService(ingestion_service, storage, splitter)
    org_id, owner_id, job_id = _ids()
    # Cancel right before the second part is processed.
    call_count = {"n": 0}

    def should_cancel():
        call_count["n"] += 1
        return call_count["n"] > 1

    with pytest.raises(IngestionCancelled):
        service.ingest(org_id, owner_id, job_id, "big.pdf", _SOURCE_PATH, should_cancel=should_cancel)

    assert ingestion_service.ingest.call_count == 1
