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
                # Populated only for an ingestion that goes through PdfSplitIngestionService
                # (app/application/pdf_split_ingestion_service.py) — parts_total stays None until
                # the first part result arrives, since it isn't known before ingestion starts
                # (splitting requires parsing the PDF's page count first). parts_total == 1 means
                # "ordinary single-document ingestion", same meaning as document_id above being
                # the only thing set; parts_total > 1 means a PDF actually got split.
                "document_ids": [],
                "parts_total": None,
                "parts_completed": 0,
                "parts_failed": 0,
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
    def set_parts_total(job_id: str, parts_total: int):
        with _lock:
            _jobs[job_id]["parts_total"] = parts_total

    @staticmethod
    def mark_part_completed(job_id: str, document_id):
        with _lock:
            _jobs[job_id]["document_ids"].append(str(document_id))
            _jobs[job_id]["parts_completed"] += 1

    @staticmethod
    def mark_part_failed(job_id: str, error: Exception):
        with _lock:
            _jobs[job_id]["parts_failed"] += 1
            # Last error wins — enough for a client to know something went wrong; per-part detail
            # is available by listing the org's documents and inspecting each failed part's own
            # error_message.
            _jobs[job_id]["error"] = str(error)

    @staticmethod
    def mark_completed_with_parts(job_id: str):
        with _lock:
            _jobs[job_id]["status"] = "completed"

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
