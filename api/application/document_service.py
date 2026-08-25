import logging
from uuid import UUID

from api.domain import error_codes
from api.domain.entities import Chunk, Document
from api.domain.errors import NotFoundError, ValidationError
from api.domain.ports import CategoryRepositoryPort, ChunkRepositoryPort, DocumentRepositoryPort, IngestionJobRepositoryPort

logger = logging.getLogger(__name__)

# ingestion_jobs.status (queued/processing/indexed/failed) is the ORM/worker-facing vocabulary --
# GET /jobs and GET /crawl-jobs have their own, older, caller-facing one (pending/running/
# completed/failed) that predates this table becoming the source of truth (it used to be
# JobStore/CrawlJobStore's in-memory vocabulary — see this repo's ingestion-worker Release 1/2
# history). Mapped here rather than changed at the ORM/enum level so the response contract
# webui/src/lib/useJobPolling.ts already depends on (its own hardcoded TERMINAL_STATUSES) doesn't
# need to change. No separate "cancelled" status exists in the enum -- a cancelled job settles as
# "failed" with "Cancelled by user." in error_message, same as any other failure.
_STATUS_TO_RESPONSE = {"queued": "pending", "processing": "running", "indexed": "completed", "failed": "failed"}


def _job_status_response(job) -> dict:
    return {
        "status": _STATUS_TO_RESPONSE[job.status],
        "error": job.error_message,
        "document_id": str(job.document_id) if job.document_id else None,
        "cancel_requested": job.cancel_requested,
        "document_ids": job.document_ids,
        "parts_total": job.parts_total,
        "parts_completed": job.parts_completed,
        "parts_failed": job.parts_failed,
    }


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        ingestion_job_repo: IngestionJobRepositoryPort | None = None,
        category_repo: CategoryRepositoryPort | None = None,
    ):
        self._documents = document_repo
        self._chunks = chunk_repo
        # Optional: only the job-creation/status/cancel methods below need this. Actual ingestion
        # execution lives entirely in api/ingestion_worker/ now, which claims and processes queued
        # rows from its own independent process -- this service only ever enqueues and reads.
        self._ingestion_jobs = ingestion_job_repo
        # Optional: only update_metadata() needs it, to check a caller-supplied category_id
        # actually belongs to this org before writing it onto the document.
        self._categories = category_repo

    def list_documents(
        self,
        org_id: UUID,
        limit: int,
        offset: int,
        sort: str,
        category_id: UUID | None = None,
        shelf_id: UUID | None = None,
        document_type: str | None = None,
    ) -> tuple[list[Document], int]:
        return (
            self._documents.list_for_org(
                org_id, limit, offset, sort, category_id=category_id, shelf_id=shelf_id, document_type=document_type
            ),
            self._documents.count_for_org(org_id, category_id=category_id, shelf_id=shelf_id, document_type=document_type),
        )

    def get_document(self, org_id: UUID, document_id: UUID) -> Document:
        document = self._documents.get(document_id)
        if document is None or document.org_id != org_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")
        return document

    def list_chunks(self, org_id: UUID, document_id: UUID, limit: int, offset: int) -> list[Chunk]:
        self.get_document(org_id, document_id)
        return self._chunks.list_for_document(document_id, limit, offset)

    def delete_document(self, org_id: UUID, document_id: UUID) -> None:
        document = self._documents.get(document_id)
        if document is None or document.org_id != org_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")

        chunk_count = self._chunks.count_for_document(document_id)
        self._documents.delete(document_id)
        logger.info(
            "Document deleted",
            extra={"org_id": str(org_id), "document_id": str(document_id), "chunk_count": chunk_count},
        )

    def rename_document(self, org_id: UUID, document_id: UUID, new_name: str) -> Document:
        document = self._documents.get(document_id)
        if document is None or document.org_id != org_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")
        return self._documents.rename(document_id, new_name)

    def update_metadata(
        self, org_id: UUID, document_id: UUID, category_id: UUID | None, document_type: str
    ) -> Document:
        document = self._documents.get(document_id)
        if document is None or document.org_id != org_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")
        if category_id is not None:
            category = self._categories.get(category_id)
            if category is None or category.org_id != org_id:
                raise NotFoundError(error_codes.CATEGORY_NOT_FOUND, "Category not found.")
        return self._documents.update_metadata(document_id, category_id, document_type)

    def get_job_status(self, org_id: UUID, job_id: str) -> dict:
        job = self._get_owned_job(org_id, job_id, {"upload", "reindex"}, error_codes.JOB_NOT_FOUND, "Job not found.")
        return _job_status_response(job)

    def cancel_job(self, org_id: UUID, job_id: str) -> None:
        """Best-effort: the worker only checks cancel_requested between embedding batches, not
        instantly — see JobStatusResponse's cancel_requested field and this method's route
        docstring (api/presentation/routes/documents.py)."""
        job = self._get_owned_job(org_id, job_id, {"upload", "reindex"}, error_codes.JOB_NOT_FOUND, "Job not found.")
        self._ingestion_jobs.request_cancellation(job.id)
        self._ingestion_jobs.commit()

    def start_ingestion(
        self,
        org_id: UUID,
        owner_id: UUID,
        filename: str,
        payload_path: str,
        job_id: UUID,
        category_id: UUID | None = None,
    ) -> str:
        """Enqueues the job and returns immediately -- api/ingestion_worker/'s standalone process
        claims and processes queued rows independently, on its own schedule. This method does no
        ingestion work itself.

        job_id is pre-generated by the caller (the route), which needs it up front to know where
        to stream the upload to on disk (UploadStorage.path_for_job_upload) before this job row
        even exists -- payload_path is that same path, already written by the time this is
        called."""
        job = self._ingestion_jobs.create(
            org_id,
            type="upload",
            id=job_id,
            triggered_by=owner_id,
            payload_path=payload_path,
            payload_filename=filename,
            category_id=category_id,
        )
        self._ingestion_jobs.commit()
        logger.info(
            "Ingestion job created",
            extra={"job_id": str(job.id), "org_id": str(org_id), "source_filename": filename},
        )
        return str(job.id)

    def start_retry(self, org_id: UUID, document_id: UUID, owner_id: UUID) -> str:
        document = self._documents.get(document_id)
        if document is None or document.org_id != org_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")
        if document.status != "failed":
            raise ValidationError(
                error_codes.DOCUMENT_NOT_RETRYABLE,
                f"Only failed documents can be retried (current status: '{document.status}').",
                field="document_id",
            )

        job = self._ingestion_jobs.create(org_id, type="reindex", document_id=document_id, triggered_by=owner_id)
        self._ingestion_jobs.commit()
        logger.info(
            "Retry job created",
            extra={"job_id": str(job.id), "org_id": str(org_id), "document_id": str(document_id)},
        )
        return str(job.id)

    def start_crawl(
        self,
        org_id: UUID,
        owner_id: UUID,
        url: str,
        max_pages: int,
        scope_prefix: str | None,
        category_id: UUID | None = None,
    ) -> str:
        job = self._ingestion_jobs.create(
            org_id,
            type="crawl",
            triggered_by=owner_id,
            crawl_url=url,
            crawl_max_pages=max_pages,
            crawl_scope_prefix=scope_prefix,
            category_id=category_id,
        )
        self._ingestion_jobs.commit()
        logger.info(
            "Crawl job created",
            extra={"job_id": str(job.id), "org_id": str(org_id), "seed_url": url, "max_pages": max_pages},
        )
        return str(job.id)

    def get_crawl_job_status(self, org_id: UUID, job_id: str) -> dict:
        job = self._get_owned_job(
            org_id, job_id, {"crawl"}, error_codes.CRAWL_JOB_NOT_FOUND, "Crawl job not found."
        )
        return {
            "status": _STATUS_TO_RESPONSE[job.status],
            "seed_url": job.crawl_url,
            "error": job.error_message,
            "pages": job.pages,
        }

    def _get_owned_job(self, org_id: UUID, job_id: str, allowed_types: set[str], error_code: str, message: str):
        try:
            job_uuid = UUID(job_id)
        except ValueError as error:
            raise NotFoundError(error_code, message) from error
        job = self._ingestion_jobs.get(job_uuid)
        # 404, not 403 — same as DocumentRepository's org-isolation pattern elsewhere in this
        # service: doesn't confirm to an unauthorized caller that the job exists at all. Also
        # 404s a real job of the *wrong kind* for this route (e.g. a crawl job id passed to
        # GET /jobs) rather than exposing one route's job through the other's response shape.
        if job is None or job.org_id != org_id or job.type not in allowed_types:
            raise NotFoundError(error_code, message)
        return job
