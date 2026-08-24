import logging
import threading
from datetime import datetime, timezone
from uuid import UUID

from api.application.crawl_job_store import CrawlJobNotFoundError, CrawlJobStore
from api.application.ingestion_service import IngestionService
from api.application.job_store import JobNotFoundError, JobStore
from api.application.pdf_split_ingestion_service import PdfSplitIngestionService
from api.application.web_crawl_service import WebCrawlService
from api.constants import DEFAULT_WEB_CRAWL_USER_AGENT
from api.domain import error_codes
from api.domain.entities import Chunk, Document
from api.domain.errors import IngestionCancelled, NotFoundError, ValidationError
from api.domain.ports import CategoryRepositoryPort, ChunkRepositoryPort, DocumentRepositoryPort, IngestionJobRepositoryPort
from api.infrastructure.orm import SessionLocal
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.web.fetcher import WebPageFetcher
from api.logging_config import clear_job_id, set_job_id

logger = logging.getLogger(__name__)

# JobStore's in-process vocabulary (pending/running/completed/cancelled/failed) doesn't line up
# 1:1 with the persisted `ingestion_jobs.status` enum (queued/processing/indexed/failed) — the
# latter has no "cancelled" state (adding one is a real migration, out of scope for what's meant
# to be a best-effort durable side-record, not a replacement — see document_service.py's module
# docstring-equivalent note in the plan). Cancellation maps to "failed" with an explanatory message.
_PERSISTED_STATUS_RUNNING = "processing"
_PERSISTED_STATUS_DONE = "indexed"
_PERSISTED_STATUS_FAILED = "failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _persist_job_status(session, ingestion_jobs: IngestionJobRepository, ingestion_job_id: UUID, status: str, **fields):
    """Best-effort write to the durable ingestion_jobs side-record (see A.4 in the plan) — never
    raises. JobStore (in-memory) is the authoritative source of truth the live polling UX depends
    on; this is a secondary record for history/dashboard views, so a failure here (including one
    encountered while already handling a different failure) must never crash the ingestion
    thread or mask the original error."""
    try:
        ingestion_jobs.update_status(ingestion_job_id, status, **fields)
        session.commit()
    except Exception:
        session.rollback()
        logger.warning(
            "Failed to persist ingestion job status", extra={"ingestion_job_id": str(ingestion_job_id)}, exc_info=True
        )


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
        # Optional: only the request-thread construction (documents.py's _service()) needs this,
        # to create the initial persisted row before handing off to a background thread. The
        # background thread itself builds its own IngestionJobRepository against its own session
        # (see _run_ingestion_job etc.) rather than sharing this one across threads.
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
        try:
            status = JobStore.get(job_id)
        except JobNotFoundError as error:
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.") from error
        # 404, not 403 — same as DocumentRepository's org-isolation pattern elsewhere in this
        # service: doesn't confirm to an unauthorized caller that the job exists at all.
        if status["org_id"] != str(org_id):
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.")
        return status

    def cancel_job(self, org_id: UUID, job_id: str) -> None:
        try:
            status = JobStore.get(job_id)
        except JobNotFoundError as error:
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.") from error
        if status["org_id"] != str(org_id):
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.")
        JobStore.request_cancellation(job_id)

    def start_ingestion(
        self,
        org_id: UUID,
        owner_id: UUID,
        filename: str,
        file_bytes: bytes,
        category_id: UUID | None = None,
    ) -> str:
        job_id = JobStore.create(org_id)
        ingestion_job_id = self._ingestion_jobs.create(org_id, type="upload", triggered_by=owner_id).id
        # Commits the row before handing off below — the background thread opens its own
        # independent session (see _run_ingestion_job), which can't see an uncommitted row from
        # this one (READ COMMITTED). Without this, its first update_status() call races the
        # request thread's own eventual commit at teardown and can find no row at all.
        self._ingestion_jobs.commit()
        # Logged on the *request* thread, so this line also carries request_id from the context
        # filter — the bridge that lets you grep by request_id to find when a job was created,
        # then by job_id to follow the rest of its lifecycle on the background thread below.
        logger.info(
            "Ingestion job created",
            extra={"job_id": job_id, "org_id": str(org_id), "source_filename": filename},
        )
        thread = threading.Thread(
            target=_run_ingestion_job,
            args=(job_id, ingestion_job_id, org_id, owner_id, filename, file_bytes, category_id),
            daemon=True,
        )
        thread.start()
        return job_id

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

        job_id = JobStore.create(org_id)
        ingestion_job_id = self._ingestion_jobs.create(
            org_id, type="reindex", document_id=document_id, triggered_by=owner_id
        ).id
        # See start_ingestion's identical comment above — same cross-thread visibility race.
        self._ingestion_jobs.commit()
        logger.info(
            "Retry job created",
            extra={"job_id": job_id, "org_id": str(org_id), "document_id": str(document_id)},
        )
        thread = threading.Thread(
            target=_run_retry_job,
            args=(job_id, ingestion_job_id, org_id, document_id),
            daemon=True,
        )
        thread.start()
        return job_id

    def start_crawl(
        self,
        org_id: UUID,
        owner_id: UUID,
        url: str,
        max_pages: int,
        scope_prefix: str | None,
        category_id: UUID | None = None,
    ) -> str:
        job_id = CrawlJobStore.create(org_id, url)
        ingestion_job_id = self._ingestion_jobs.create(org_id, type="crawl", triggered_by=owner_id).id
        # See start_ingestion's identical comment above — same cross-thread visibility race.
        self._ingestion_jobs.commit()
        logger.info(
            "Crawl job created",
            extra={"job_id": job_id, "org_id": str(org_id), "seed_url": url, "max_pages": max_pages},
        )
        thread = threading.Thread(
            target=_run_crawl_job,
            args=(job_id, ingestion_job_id, org_id, owner_id, url, max_pages, scope_prefix, category_id),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_crawl_job_status(self, org_id: UUID, job_id: str) -> dict:
        try:
            status = CrawlJobStore.get(job_id)
        except CrawlJobNotFoundError as error:
            raise NotFoundError(error_codes.CRAWL_JOB_NOT_FOUND, "Crawl job not found.") from error
        if status["org_id"] != str(org_id):
            raise NotFoundError(error_codes.CRAWL_JOB_NOT_FOUND, "Crawl job not found.")
        return status


def _run_ingestion_job(
    job_id: str,
    ingestion_job_id: UUID,
    org_id: UUID,
    owner_id: UUID,
    filename: str,
    file_bytes: bytes,
    category_id: UUID | None,
):
    # contextvars set on the request thread do not propagate into a new threading.Thread — this
    # thread gets its own fresh, empty Context, so job_id must be set here, first, using the value
    # already passed in as an argument (not inherited).
    set_job_id(job_id)
    logger.info("Ingestion job started", extra={"org_id": str(org_id), "source_filename": filename})

    # Runs on a background thread with no Flask request context, so it gets its own session
    # independent of the request-scoped one from container.get_session() (which relies on
    # flask.g, unavailable here) — and commits/rolls back that session directly.
    session = SessionLocal()
    ingestion_jobs = IngestionJobRepository(session)
    try:
        JobStore.mark_running(job_id)
        _persist_job_status(session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_RUNNING, started_at=_now())
        ingestion_service = IngestionService(
            DocumentRepository(session), ChunkRepository(session), EmbeddingSettingsRepository(session)
        )
        split_service = PdfSplitIngestionService(ingestion_service)

        # Commits after every part (like _run_crawl_job's on_page_result below) so a part that
        # ingests successfully is durably saved even if a later part in the same oversized-PDF
        # split fails. For an ordinary (non-split) upload this callback fires exactly once, with
        # parts_total == 1 — see the branching below.
        def on_part_result(part_index, parts_total, document, error):
            session.commit()
            JobStore.set_parts_total(job_id, parts_total)
            if document is not None:
                JobStore.mark_part_completed(job_id, document.id)
                logger.info(
                    "Ingestion part completed",
                    extra={"document_id": str(document.id), "split_part": part_index, "split_total": parts_total},
                )
            else:
                JobStore.mark_part_failed(job_id, error)
                logger.warning(
                    "Ingestion part failed",
                    extra={"split_part": part_index, "split_total": parts_total, "error": str(error)},
                )

        split_service.ingest(
            org_id,
            owner_id,
            filename,
            file_bytes,
            category_id=category_id,
            should_cancel=lambda: JobStore.is_cancellation_requested(job_id),
            on_part_result=on_part_result,
        )

        # split_service.ingest() only returns normally after at least one on_part_result call —
        # any failure on the ordinary single-document path raises instead (caught below), so
        # parts_total is guaranteed to be set here.
        job = JobStore.get(job_id)
        if job["parts_total"] == 1:
            document_id = job["document_ids"][0]
            JobStore.mark_completed(job_id, document_id)
            _persist_job_status(
                session,
                ingestion_jobs,
                ingestion_job_id,
                _PERSISTED_STATUS_DONE,
                document_id=document_id,
                items_processed=1,
                finished_at=_now(),
            )
            logger.info("Ingestion job completed", extra={"document_id": document_id})
        elif job["parts_completed"] > 0:
            JobStore.mark_completed_with_parts(job_id)
            _persist_job_status(
                session,
                ingestion_jobs,
                ingestion_job_id,
                _PERSISTED_STATUS_DONE,
                items_processed=job["parts_completed"],
                finished_at=_now(),
            )
            logger.info(
                "Ingestion job completed",
                extra={"parts_completed": job["parts_completed"], "parts_failed": job["parts_failed"]},
            )
        else:
            JobStore.mark_failed(job_id, RuntimeError("Every part of this PDF failed to ingest."))
            _persist_job_status(
                session,
                ingestion_jobs,
                ingestion_job_id,
                _PERSISTED_STATUS_FAILED,
                error_message="Every part of this PDF failed to ingest.",
                finished_at=_now(),
            )
            logger.error(
                "Ingestion job failed: every split part failed",
                extra={"parts_failed": job["parts_failed"]},
            )
    except IngestionCancelled:
        session.commit()
        JobStore.mark_cancelled(job_id)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_FAILED,
            error_message="Cancelled by user.", finished_at=_now(),
        )
        logger.info("Ingestion job cancelled", extra={"org_id": str(org_id), "source_filename": filename})
    except Exception as error:
        session.commit()
        JobStore.mark_failed(job_id, error)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_FAILED,
            error_message=str(error), finished_at=_now(),
        )
        logger.exception("Ingestion job failed", extra={"org_id": str(org_id), "source_filename": filename})
    finally:
        session.close()
        # Each ingestion job runs in its own daemon thread that dies once the job finishes, so
        # this isn't strictly load-bearing in production — but clearing it (mirroring
        # request_id's token-based reset in api/__init__.py's teardown_request) is correct
        # regardless, and avoids leaking a stale job_id if this function is ever called directly
        # from the same thread again (e.g. in tests, which don't spawn a new thread per call).
        clear_job_id()


def _run_retry_job(job_id: str, ingestion_job_id: UUID, org_id: UUID, document_id: UUID):
    # Mirrors _run_ingestion_job's structure exactly — see that function's comments for why each
    # piece (fresh session, job_id contextvar set here not inherited, etc.) is the way it is.
    set_job_id(job_id)
    logger.info("Retry job started", extra={"org_id": str(org_id), "document_id": str(document_id)})

    session = SessionLocal()
    ingestion_jobs = IngestionJobRepository(session)
    try:
        JobStore.mark_running(job_id)
        _persist_job_status(session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_RUNNING, started_at=_now())
        document_repo = DocumentRepository(session)
        document = document_repo.get(document_id)
        ingestion_service = IngestionService(document_repo, ChunkRepository(session), EmbeddingSettingsRepository(session))
        document = ingestion_service.retry(
            document, should_cancel=lambda: JobStore.is_cancellation_requested(job_id)
        )
        session.commit()
        JobStore.mark_completed(job_id, document.id)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_DONE,
            items_processed=1, finished_at=_now(),
        )
        logger.info("Retry job completed", extra={"document_id": str(document.id)})
    except IngestionCancelled:
        session.commit()
        JobStore.mark_cancelled(job_id)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_FAILED,
            error_message="Cancelled by user.", finished_at=_now(),
        )
        logger.info("Retry job cancelled", extra={"org_id": str(org_id), "document_id": str(document_id)})
    except Exception as error:
        session.commit()
        JobStore.mark_failed(job_id, error)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_FAILED,
            error_message=str(error), finished_at=_now(),
        )
        logger.exception("Retry job failed", extra={"org_id": str(org_id), "document_id": str(document_id)})
    finally:
        session.close()
        clear_job_id()


def _run_crawl_job(
    job_id: str,
    ingestion_job_id: UUID,
    org_id: UUID,
    owner_id: UUID,
    url: str,
    max_pages: int,
    scope_prefix: str | None,
    category_id: UUID | None,
):
    # Mirrors _run_ingestion_job's structure — fresh session, job_id set here not inherited, etc.
    # Unlike a single-document job, this one commits after every page (in on_page_result below) so
    # a page that ingests successfully is durably saved even if a later page in the same crawl
    # fails, and so CrawlJobStore's per-page status reflects data that's actually persisted.
    set_job_id(job_id)
    logger.info("Crawl job started", extra={"org_id": str(org_id), "seed_url": url, "max_pages": max_pages})

    session = SessionLocal()
    ingestion_jobs = IngestionJobRepository(session)
    pages_completed = 0
    try:
        CrawlJobStore.mark_running(job_id)
        _persist_job_status(session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_RUNNING, started_at=_now())
        ingestion_service = IngestionService(
            DocumentRepository(session), ChunkRepository(session), EmbeddingSettingsRepository(session)
        )
        crawl_service = WebCrawlService(ingestion_service, WebPageFetcher(user_agent=DEFAULT_WEB_CRAWL_USER_AGENT))

        def on_page_result(page_url, document, error):
            nonlocal pages_completed
            session.commit()
            if document is not None:
                pages_completed += 1
                CrawlJobStore.mark_page_completed(job_id, page_url, document.id)
                logger.info("Crawl page completed", extra={"url": page_url, "document_id": str(document.id)})
            else:
                CrawlJobStore.mark_page_failed(job_id, page_url, error)
                logger.warning("Crawl page failed", extra={"url": page_url, "error": str(error)})

        crawl_service.crawl(
            org_id, owner_id, url, max_pages, category_id=category_id, scope_prefix=scope_prefix,
            on_page_result=on_page_result,
        )
        CrawlJobStore.mark_completed(job_id)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_DONE,
            items_processed=pages_completed, finished_at=_now(),
        )
        logger.info("Crawl job completed", extra={"seed_url": url})
    except Exception as error:
        session.commit()
        CrawlJobStore.mark_failed(job_id, error)
        _persist_job_status(
            session, ingestion_jobs, ingestion_job_id, _PERSISTED_STATUS_FAILED,
            error_message=str(error), items_processed=pages_completed, finished_at=_now(),
        )
        logger.exception("Crawl job failed", extra={"org_id": str(org_id), "seed_url": url})
    finally:
        session.close()
        clear_job_id()
