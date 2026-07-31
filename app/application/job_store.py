import threading
import uuid

_lock = threading.Lock()
_jobs = {}


class JobNotFoundError(KeyError):
    pass


class JobStore:
    """In-memory ingestion job status tracker.

    v1 keeps this single-process/in-memory since ingestion is a manual, one-at-a-time user
    action (no background watching). Move to Celery/Redis if ingestion volume grows enough to
    need multiple worker processes.
    """

    @staticmethod
    def create() -> str:
        job_id = str(uuid.uuid4())
        with _lock:
            _jobs[job_id] = {
                "status": "pending",
                "error": None,
                "document_id": None,
                "cancel_requested": False,
            }
        return job_id

    @staticmethod
    def mark_running(job_id: str):
        with _lock:
            _jobs[job_id]["status"] = "running"

    @staticmethod
    def mark_completed(job_id: str, document_id):
        with _lock:
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["document_id"] = str(document_id)

    @staticmethod
    def mark_failed(job_id: str, error: Exception):
        with _lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(error)

    @staticmethod
    def mark_cancelled(job_id: str):
        with _lock:
            _jobs[job_id]["status"] = "cancelled"

    @staticmethod
    def request_cancellation(job_id: str):
        with _lock:
            if job_id not in _jobs:
                raise JobNotFoundError(job_id)
            _jobs[job_id]["cancel_requested"] = True

    @staticmethod
    def is_cancellation_requested(job_id: str) -> bool:
        with _lock:
            job = _jobs.get(job_id)
            return job is not None and job["cancel_requested"]

    @staticmethod
    def get(job_id: str) -> dict:
        with _lock:
            if job_id not in _jobs:
                raise JobNotFoundError(job_id)
            return dict(_jobs[job_id])
