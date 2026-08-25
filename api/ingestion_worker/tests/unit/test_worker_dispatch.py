from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.ingestion_worker.worker import IngestionJobWorker


def _fake_job(job_type):
    job = MagicMock()
    job.id = uuid4()
    job.org_id = uuid4()
    job.type = job_type
    return job


def _claim_and_process(job):
    """Runs claim_and_process_one() with IngestionJobRepository patched to hand back a mock that
    claims the given job (or None, for the empty-queue case) — returns
    (worker, claimed, session, ingestion_jobs) for assertions."""
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    ingestion_jobs = MagicMock()
    ingestion_jobs.claim_next_queued.return_value = job

    worker = IngestionJobWorker(session_factory=session_factory)
    worker._process_upload = MagicMock()
    worker._process_retry = MagicMock()
    worker._process_crawl = MagicMock()

    with patch("api.ingestion_worker.worker.IngestionJobRepository", return_value=ingestion_jobs):
        claimed = worker.claim_and_process_one()
    return worker, claimed, session, ingestion_jobs


def test_claim_and_process_one_returns_false_when_queue_empty():
    worker, claimed, session, _ingestion_jobs = _claim_and_process(None)

    assert claimed is False
    session.close.assert_called_once()


def test_dispatches_upload_to_process_upload():
    job = _fake_job("upload")
    worker, claimed, session, ingestion_jobs = _claim_and_process(job)

    assert claimed is True
    worker._process_upload.assert_called_once_with(session, ingestion_jobs, job)
    worker._process_retry.assert_not_called()
    worker._process_crawl.assert_not_called()
    session.close.assert_called_once()


def test_dispatches_reindex_to_process_retry():
    job = _fake_job("reindex")
    worker, claimed, session, ingestion_jobs = _claim_and_process(job)

    assert claimed is True
    worker._process_retry.assert_called_once_with(session, ingestion_jobs, job)
    worker._process_upload.assert_not_called()
    worker._process_crawl.assert_not_called()


def test_dispatches_crawl_to_process_crawl():
    job = _fake_job("crawl")
    worker, claimed, session, ingestion_jobs = _claim_and_process(job)

    assert claimed is True
    worker._process_crawl.assert_called_once_with(session, ingestion_jobs, job)
    worker._process_upload.assert_not_called()
    worker._process_retry.assert_not_called()


def test_unknown_job_type_marks_failed_without_dispatching():
    job = _fake_job("resync")
    worker, claimed, session, ingestion_jobs = _claim_and_process(job)

    assert claimed is True
    worker._process_upload.assert_not_called()
    worker._process_retry.assert_not_called()
    worker._process_crawl.assert_not_called()
    ingestion_jobs.update_status.assert_called_once()
    assert ingestion_jobs.update_status.call_args.args[0] == job.id
    assert ingestion_jobs.update_status.call_args.args[1] == "failed"
    session.commit.assert_called_once()


def test_gc_collect_runs_after_a_processed_job_but_not_on_an_empty_queue(monkeypatch):
    """Regression test for the production OOM investigation: a job's PDF-parsing reference cycles
    should be forced to collect right after that job finishes, not left to the collector's own
    thresholds (see worker.py's comment on this gc.collect() call) -- and only when a job was
    actually processed, not on every empty-queue poll."""
    calls = []
    monkeypatch.setattr("api.ingestion_worker.worker.gc.collect", lambda: calls.append(1))

    _claim_and_process(_fake_job("upload"))
    assert calls == [1]

    calls.clear()
    _claim_and_process(None)
    assert calls == []


def test_run_forever_sleeps_only_when_nothing_claimed(monkeypatch):
    worker = IngestionJobWorker(session_factory=MagicMock(), poll_interval_s=0.01)
    calls = {"n": 0}

    def fake_claim_and_process_one():
        calls["n"] += 1
        return calls["n"] < 3  # claim twice, then an empty queue

    worker.claim_and_process_one = fake_claim_and_process_one
    sleeps = []
    monkeypatch.setattr("api.ingestion_worker.worker.time.sleep", lambda s: sleeps.append(s))

    stop_after = {"n": 0}

    def should_stop():
        stop_after["n"] += 1
        return stop_after["n"] > 3

    worker.run_forever(should_stop=should_stop)

    assert calls["n"] == 3
    assert sleeps == [0.01]  # only the empty-queue iteration slept
