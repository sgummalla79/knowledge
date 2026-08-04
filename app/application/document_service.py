import logging
import threading
from uuid import UUID

from app.application.crawl_job_store import CrawlJobNotFoundError, CrawlJobStore
from app.application.ingestion_service import IngestionService
from app.application.job_store import JobNotFoundError, JobStore
from app.application.pdf_split_ingestion_service import PdfSplitIngestionService
from app.application.web_crawl_service import WebCrawlService
from app.application.web_crawl_settings_service import WebCrawlSettingsService
from app.domain import error_codes
from app.domain.entities import Document
from app.domain.errors import IngestionCancelled, NotFoundError, ValidationError
from app.domain.ports import ChunkRepositoryPort, DocumentRepositoryPort, LibraryRepositoryPort
from app.infrastructure.orm import SessionLocal
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.library_repository import LibraryRepository
from app.infrastructure.repositories.web_crawl_settings_repository import WebCrawlSettingsRepository
from app.infrastructure.web.fetcher import WebPageFetcher
from app.logging_config import clear_job_id, set_job_id

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        library_repo: LibraryRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
    ):
        self._documents = document_repo
        self._libraries = library_repo
        self._chunks = chunk_repo

    def list_documents(self, library_id: UUID, limit: int, offset: int, sort: str) -> tuple[list[Document], int]:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        return (
            self._documents.list_for_library(library_id, limit, offset, sort),
            self._documents.count_for_library(library_id),
        )

    def delete_document(self, library_id: UUID, document_id: UUID) -> None:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        document = self._documents.get(document_id)
        if document is None or document.library_id != library_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")

        chunk_count = self._chunks.count_for_document(document_id)
        self._documents.delete(document_id)
        self._libraries.increment_counts(library_id, document_delta=-1, chunk_delta=-chunk_count)
        logger.info(
            "Document deleted",
            extra={"library_id": str(library_id), "document_id": str(document_id), "chunk_count": chunk_count},
        )

    def rename_document(self, library_id: UUID, document_id: UUID, new_name: str) -> Document:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        document = self._documents.get(document_id)
        if document is None or document.library_id != library_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")
        return self._documents.rename(document_id, new_name)

    def get_job_status(self, job_id: str) -> dict:
        try:
            return JobStore.get(job_id)
        except JobNotFoundError as error:
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.") from error

    def cancel_job(self, job_id: str) -> None:
        try:
            JobStore.request_cancellation(job_id)
        except JobNotFoundError as error:
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.") from error

    def start_ingestion(self, library_id: UUID, filename: str, file_bytes: bytes) -> str:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")

        job_id = JobStore.create()
        # Logged on the *request* thread, so this line also carries request_id from the context
        # filter — the bridge that lets you grep by request_id to find when a job was created,
        # then by job_id to follow the rest of its lifecycle on the background thread below.
        logger.info(
            "Ingestion job created",
            extra={"job_id": job_id, "library_id": str(library_id), "source_filename": filename},
        )
        thread = threading.Thread(
            target=_run_ingestion_job,
            args=(job_id, library_id, filename, file_bytes),
            daemon=True,
        )
        thread.start()
        return job_id

    def start_retry(self, library_id: UUID, document_id: UUID) -> str:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        document = self._documents.get(document_id)
        if document is None or document.library_id != library_id:
            raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")
        if document.status not in ("failed", "cancelled"):
            raise ValidationError(
                error_codes.DOCUMENT_NOT_RETRYABLE,
                f"Only failed or cancelled documents can be retried (current status: '{document.status}').",
                field="document_id",
            )

        job_id = JobStore.create()
        logger.info(
            "Retry job created",
            extra={"job_id": job_id, "library_id": str(library_id), "document_id": str(document_id)},
        )
        thread = threading.Thread(
            target=_run_retry_job,
            args=(job_id, library_id, document_id),
            daemon=True,
        )
        thread.start()
        return job_id

    def start_crawl(self, library_id: UUID, url: str, max_pages: int, scope_prefix: str | None) -> str:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")

        job_id = CrawlJobStore.create(url)
        logger.info(
            "Crawl job created",
            extra={"job_id": job_id, "library_id": str(library_id), "seed_url": url, "max_pages": max_pages},
        )
        thread = threading.Thread(
            target=_run_crawl_job,
            args=(job_id, library_id, url, max_pages, scope_prefix),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_crawl_job_status(self, job_id: str) -> dict:
        try:
            return CrawlJobStore.get(job_id)
        except CrawlJobNotFoundError as error:
            raise NotFoundError(error_codes.CRAWL_JOB_NOT_FOUND, "Crawl job not found.") from error


def _run_ingestion_job(job_id: str, library_id: UUID, filename: str, file_bytes: bytes):
    # contextvars set on the request thread do not propagate into a new threading.Thread — this
    # thread gets its own fresh, empty Context, so job_id must be set here, first, using the value
    # already passed in as an argument (not inherited).
    set_job_id(job_id)
    logger.info(
        "Ingestion job started", extra={"library_id": str(library_id), "source_filename": filename}
    )

    # Runs on a background thread with no Flask request context, so it gets its own session
    # independent of the request-scoped one from container.get_session() (which relies on
    # flask.g, unavailable here) — and commits/rolls back that session directly.
    session = SessionLocal()
    try:
        JobStore.mark_running(job_id)
        library_repo = LibraryRepository(session)
        library = library_repo.get(library_id)
        ingestion_service = IngestionService(
            library_repo,
            DocumentRepository(session),
            ChunkRepository(session),
            EmbeddingSettingsRepository(session),
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
            library,
            filename,
            file_bytes,
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
            logger.info("Ingestion job completed", extra={"document_id": document_id})
        elif job["parts_completed"] > 0:
            JobStore.mark_completed_with_parts(job_id)
            logger.info(
                "Ingestion job completed",
                extra={"parts_completed": job["parts_completed"], "parts_failed": job["parts_failed"]},
            )
        else:
            JobStore.mark_failed(job_id, RuntimeError("Every part of this PDF failed to ingest."))
            logger.error(
                "Ingestion job failed: every split part failed",
                extra={"parts_failed": job["parts_failed"]},
            )
    except IngestionCancelled:
        session.commit()
        JobStore.mark_cancelled(job_id)
        logger.info(
            "Ingestion job cancelled", extra={"library_id": str(library_id), "source_filename": filename}
        )
    except Exception as error:
        session.commit()
        JobStore.mark_failed(job_id, error)
        logger.exception(
            "Ingestion job failed", extra={"library_id": str(library_id), "source_filename": filename}
        )
    finally:
        session.close()
        # Each ingestion job runs in its own daemon thread that dies once the job finishes, so
        # this isn't strictly load-bearing in production — but clearing it (mirroring
        # request_id's token-based reset in app/__init__.py's teardown_request) is correct
        # regardless, and avoids leaking a stale job_id if this function is ever called directly
        # from the same thread again (e.g. in tests, which don't spawn a new thread per call).
        clear_job_id()


def _run_retry_job(job_id: str, library_id: UUID, document_id: UUID):
    # Mirrors _run_ingestion_job's structure exactly — see that function's comments for why each
    # piece (fresh session, job_id contextvar set here not inherited, etc.) is the way it is.
    set_job_id(job_id)
    logger.info("Retry job started", extra={"library_id": str(library_id), "document_id": str(document_id)})

    session = SessionLocal()
    try:
        JobStore.mark_running(job_id)
        library_repo = LibraryRepository(session)
        document_repo = DocumentRepository(session)
        library = library_repo.get(library_id)
        document = document_repo.get(document_id)
        ingestion_service = IngestionService(
            library_repo, document_repo, ChunkRepository(session), EmbeddingSettingsRepository(session)
        )
        document = ingestion_service.retry(
            document, library, should_cancel=lambda: JobStore.is_cancellation_requested(job_id)
        )
        session.commit()
        JobStore.mark_completed(job_id, document.id)
        logger.info("Retry job completed", extra={"document_id": str(document.id)})
    except IngestionCancelled:
        session.commit()
        JobStore.mark_cancelled(job_id)
        logger.info(
            "Retry job cancelled", extra={"library_id": str(library_id), "document_id": str(document_id)}
        )
    except Exception as error:
        session.commit()
        JobStore.mark_failed(job_id, error)
        logger.exception(
            "Retry job failed", extra={"library_id": str(library_id), "document_id": str(document_id)}
        )
    finally:
        session.close()
        clear_job_id()


def _run_crawl_job(job_id: str, library_id: UUID, url: str, max_pages: int, scope_prefix: str | None):
    # Mirrors _run_ingestion_job's structure — fresh session, job_id set here not inherited, etc.
    # Unlike a single-document job, this one commits after every page (in on_page_result below) so
    # a page that ingests successfully is durably saved even if a later page in the same crawl
    # fails, and so CrawlJobStore's per-page status reflects data that's actually persisted.
    set_job_id(job_id)
    logger.info("Crawl job started", extra={"library_id": str(library_id), "seed_url": url, "max_pages": max_pages})

    session = SessionLocal()
    try:
        CrawlJobStore.mark_running(job_id)
        library_repo = LibraryRepository(session)
        library = library_repo.get(library_id)
        ingestion_service = IngestionService(
            library_repo, DocumentRepository(session), ChunkRepository(session), EmbeddingSettingsRepository(session)
        )
        web_crawl_settings = WebCrawlSettingsService(WebCrawlSettingsRepository(session)).get_status()
        crawl_service = WebCrawlService(ingestion_service, WebPageFetcher(user_agent=web_crawl_settings.user_agent))

        def on_page_result(page_url, document, error):
            session.commit()
            if document is not None:
                CrawlJobStore.mark_page_completed(job_id, page_url, document.id)
                logger.info("Crawl page completed", extra={"url": page_url, "document_id": str(document.id)})
            else:
                CrawlJobStore.mark_page_failed(job_id, page_url, error)
                logger.warning("Crawl page failed", extra={"url": page_url, "error": str(error)})

        crawl_service.crawl(library, url, max_pages, scope_prefix, on_page_result=on_page_result)
        CrawlJobStore.mark_completed(job_id)
        logger.info("Crawl job completed", extra={"seed_url": url})
    except Exception as error:
        session.commit()
        CrawlJobStore.mark_failed(job_id, error)
        logger.exception("Crawl job failed", extra={"library_id": str(library_id), "seed_url": url})
    finally:
        session.close()
        clear_job_id()
