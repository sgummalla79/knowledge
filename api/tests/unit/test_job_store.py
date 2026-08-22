import pytest

from api.application.job_store import JobNotFoundError, JobStore


def test_new_job_has_cancel_not_requested():
    job_id = JobStore.create()
    assert JobStore.is_cancellation_requested(job_id) is False


def test_request_cancellation_sets_flag():
    job_id = JobStore.create()
    JobStore.request_cancellation(job_id)
    assert JobStore.is_cancellation_requested(job_id) is True


def test_request_cancellation_missing_job_raises():
    with pytest.raises(JobNotFoundError):
        JobStore.request_cancellation("does-not-exist")


def test_is_cancellation_requested_missing_job_returns_false():
    # Mirrors how a job_id that never existed (or was created in a different process) should be
    # treated by should_cancel callables — never crash the pipeline over a lookup miss.
    assert JobStore.is_cancellation_requested("does-not-exist") is False


def test_mark_cancelled_sets_status():
    job_id = JobStore.create()
    JobStore.mark_cancelled(job_id)
    assert JobStore.get(job_id)["status"] == "cancelled"


def test_get_missing_job_raises():
    with pytest.raises(JobNotFoundError):
        JobStore.get("does-not-exist")


def test_new_job_has_no_parts_tracked_yet():
    job_id = JobStore.create()
    job = JobStore.get(job_id)
    assert job["document_ids"] == []
    assert job["parts_total"] is None
    assert job["parts_completed"] == 0
    assert job["parts_failed"] == 0


def test_mark_part_completed_appends_document_id_and_increments_count():
    job_id = JobStore.create()
    doc_id = "11111111-1111-1111-1111-111111111111"
    JobStore.mark_part_completed(job_id, doc_id)
    job = JobStore.get(job_id)
    assert job["document_ids"] == [doc_id]
    assert job["parts_completed"] == 1


def test_mark_part_failed_increments_count_and_sets_error():
    job_id = JobStore.create()
    JobStore.mark_part_failed(job_id, RuntimeError("boom"))
    job = JobStore.get(job_id)
    assert job["parts_failed"] == 1
    assert job["error"] == "boom"


def test_mark_completed_with_parts_sets_status():
    job_id = JobStore.create()
    JobStore.set_parts_total(job_id, 3)
    JobStore.mark_part_completed(job_id, "doc-1")
    JobStore.mark_completed_with_parts(job_id)
    job = JobStore.get(job_id)
    assert job["status"] == "completed"
    assert job["parts_total"] == 3
