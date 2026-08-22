import threading
import uuid

_lock = threading.Lock()
_jobs = {}


class CrawlJobNotFoundError(KeyError):
    pass


class CrawlJobStore:
    """In-memory crawl job status tracker — same "v1 single-process" rationale as JobStore
    (api/application/job_store.py), shaped for a job that produces many documents instead of one:
    tracks per-page status under a single job_id so a caller can watch a multi-page crawl progress
    without polling once per page."""

    @staticmethod
    def create(org_id, seed_url: str) -> str:
        job_id = str(uuid.uuid4())
        with _lock:
            _jobs[job_id] = {
                "status": "pending",
                # Not part of CrawlJobStatusResponse — checked by document_service's
                # get_crawl_job_status before a caller ever sees this job, same isolation pattern
                # DocumentRepository.get()'s callers already use.
                "org_id": str(org_id),
                "seed_url": seed_url,
                "error": None,
                "pages": {},
            }
        return job_id

    @staticmethod
    def mark_running(job_id: str):
        with _lock:
            _jobs[job_id]["status"] = "running"

    @staticmethod
    def mark_page_pending(job_id: str, url: str):
        with _lock:
            _jobs[job_id]["pages"][url] = {"status": "pending", "document_id": None, "error": None}

    @staticmethod
    def mark_page_completed(job_id: str, url: str, document_id):
        with _lock:
            _jobs[job_id]["pages"][url] = {
                "status": "completed",
                "document_id": str(document_id),
                "error": None,
            }

    @staticmethod
    def mark_page_failed(job_id: str, url: str, error: Exception):
        with _lock:
            _jobs[job_id]["pages"][url] = {"status": "failed", "document_id": None, "error": str(error)}

    @staticmethod
    def mark_completed(job_id: str):
        with _lock:
            _jobs[job_id]["status"] = "completed"

    @staticmethod
    def mark_failed(job_id: str, error: Exception):
        with _lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(error)

    @staticmethod
    def get(job_id: str) -> dict:
        with _lock:
            if job_id not in _jobs:
                raise CrawlJobNotFoundError(job_id)
            return dict(_jobs[job_id])
