import pytest

from app.application.job_store import JobNotFoundError, JobStore


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
