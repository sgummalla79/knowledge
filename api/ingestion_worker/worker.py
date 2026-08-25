"""Standalone claim-and-process loop for ingestion_jobs -- the only place ingestion actually runs
now (Release 2 of moving ingestion off the request-serving process; Release 1 built this module
inert, at replicas: 0, alongside the old threading.Thread-based path in document_service.py, which
Release 2 then deleted in the same cutover that scaled this worker up for real).

api/application/document_service.py only ever enqueues a row now (start_ingestion/start_retry/
start_crawl) and reads/cancels one (get_job_status/get_crawl_job_status/cancel_job) -- it does no
ingestion work itself and has no JobStore/CrawlJobStore to coordinate with. This module owns the
entire "how a queued job actually gets processed" responsibility on its own.
"""

import gc
import logging
import os
import socket
import time
from datetime import datetime, timezone
from typing import Callable

from api.application.ingestion_service import IngestionService
from api.application.pdf_split_ingestion_service import PdfSplitIngestionService
from api.application.web_crawl_service import WebCrawlService
from api.constants import DEFAULT_WEB_CRAWL_USER_AGENT
from api.domain.entities import IngestionJob
from api.domain.errors import IngestionCancelled
from api.infrastructure.orm import SessionLocal
from api.infrastructure.parsing.pdf_splitter import PdfSplitter
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.web.fetcher import WebPageFetcher
from api.logging_config import clear_job_id, set_job_id

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IngestionJobWorker:
    def __init__(
        self,
        session_factory=SessionLocal,
        worker_id: str | None = None,
        poll_interval_s: float = 2.0,
        pdf_splitter: PdfSplitter | None = None,
    ):
        self._session_factory = session_factory
        self._worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self._poll_interval_s = poll_interval_s
        # Injectable purely for tests -- a real small PDF can be made to trigger a multi-part
        # split without needing a genuinely MAX_UPLOAD_MB-sized fixture, same DI pattern
        # PdfSplitIngestionService's own test suite already uses (see
        # api/tests/integration/test_pdf_split_ingestion.py's _make_split_service).
        self._pdf_splitter = pdf_splitter

    def run_forever(self, should_stop: Callable[[], bool] = lambda: False) -> None:
        logger.info("Ingestion worker started", extra={})
        while not should_stop():
            if not self.claim_and_process_one():
                time.sleep(self._poll_interval_s)
        logger.info("Ingestion worker stopped", extra={})

    def claim_and_process_one(self) -> bool:
        """Returns True if a job was claimed (whether it ultimately succeeded or failed) so
        run_forever knows not to sleep before checking for the next one; False if the queue was
        empty, so run_forever backs off for poll_interval_s."""
        session = self._session_factory()
        ingestion_jobs = IngestionJobRepository(session)
        try:
            job = ingestion_jobs.claim_next_queued(self._worker_id)
            if job is None:
                return False
            set_job_id(str(job.id))
            try:
                dispatch = {
                    "upload": self._process_upload,
                    "reindex": self._process_retry,
                    "crawl": self._process_crawl,
                }.get(job.type)
                if dispatch is None:
                    logger.error("Unknown ingestion job type", extra={"org_id": str(job.org_id)})
                    ingestion_jobs.update_status(
                        job.id, "failed", error_message=f"Unknown job type: {job.type}", finished_at=_now()
                    )
                    session.commit()
                else:
                    dispatch(session, ingestion_jobs, job)
            finally:
                clear_job_id()
        finally:
            session.close()
        # PDF parsing (pdfplumber/pdfminer) builds a large per-page object graph full of
        # parent-child back-references -- reference cycles that need Python's generational
        # collector, not plain refcounting, to reclaim. Left to the collector's own thresholds,
        # this process can carry unreclaimed heap from one job into the next; a long-lived worker
        # processing several large documents back-to-back was confirmed OOM-killed in production
        # by memory that ratcheted up job-over-job even though no single job's data outlived it.
        # Forcing a collection right after a job finishes (not on every empty poll -- this line is
        # only reached once a job was actually claimed and processed) reclaims those cycles before
        # the next job's peak usage stacks on top of them.
        gc.collect()
        return True

    def _process_upload(self, session, ingestion_jobs: IngestionJobRepository, job: IngestionJob) -> None:
        logger.info(
            "Ingestion job started", extra={"org_id": str(job.org_id), "source_filename": job.payload_filename}
        )
        try:
            payload = ingestion_jobs.get_payload(job.id)
            ingestion_service = IngestionService(
                DocumentRepository(session), ChunkRepository(session), EmbeddingSettingsRepository(session)
            )
            split_service = PdfSplitIngestionService(ingestion_service, self._pdf_splitter)

            # Commits after every part -- both the document/chunks split_service.ingest() just
            # wrote AND this callback's own progress-tracking update -- so a part that ingests
            # successfully is durably saved (data and progress alike) even if a later part in the
            # same oversized-PDF split fails, or the worker process crashes mid-job.
            def on_part_result(part_index, parts_total, document, error):
                session.commit()
                ingestion_jobs.set_parts_total(job.id, parts_total)
                if document is not None:
                    ingestion_jobs.increment_parts_completed(job.id, document.id)
                    logger.info(
                        "Ingestion part completed",
                        extra={"document_id": str(document.id), "split_part": part_index, "split_total": parts_total},
                    )
                else:
                    ingestion_jobs.increment_parts_failed(job.id)
                    logger.warning(
                        "Ingestion part failed",
                        extra={"split_part": part_index, "split_total": parts_total, "error": str(error)},
                    )
                session.commit()

            split_service.ingest(
                job.org_id,
                job.triggered_by,
                job.payload_filename,
                payload,
                category_id=job.category_id,
                should_cancel=lambda: ingestion_jobs.is_cancellation_requested(job.id),
                on_part_result=on_part_result,
            )

            # split_service.ingest() only returns normally after at least one on_part_result call
            # -- any failure on the ordinary single-document path raises instead (caught below),
            # so parts_total is guaranteed to be set here (same guarantee document_service.py's
            # _run_ingestion_job already relies on).
            refreshed = ingestion_jobs.get(job.id)
            if refreshed.parts_total == 1:
                document_id = refreshed.document_ids[0]
                ingestion_jobs.update_status(
                    job.id, "indexed", document_id=document_id, items_processed=1, finished_at=_now()
                )
                logger.info("Ingestion job completed", extra={"document_id": document_id})
            elif refreshed.parts_completed > 0:
                ingestion_jobs.update_status(
                    job.id, "indexed", items_processed=refreshed.parts_completed, finished_at=_now()
                )
                logger.info(
                    "Ingestion job completed",
                    extra={"parts_completed": refreshed.parts_completed, "parts_failed": refreshed.parts_failed},
                )
            else:
                ingestion_jobs.update_status(
                    job.id, "failed", error_message="Every part of this PDF failed to ingest.", finished_at=_now()
                )
                logger.error("Ingestion job failed: every split part failed", extra={"parts_failed": refreshed.parts_failed})
            ingestion_jobs.clear_payload(job.id)
            session.commit()
        except IngestionCancelled:
            session.commit()
            ingestion_jobs.update_status(job.id, "failed", error_message="Cancelled by user.", finished_at=_now())
            ingestion_jobs.clear_payload(job.id)
            session.commit()
            logger.info(
                "Ingestion job cancelled", extra={"org_id": str(job.org_id), "source_filename": job.payload_filename}
            )
        except Exception as error:
            session.commit()
            ingestion_jobs.update_status(job.id, "failed", error_message=str(error), finished_at=_now())
            ingestion_jobs.clear_payload(job.id)
            session.commit()
            logger.exception(
                "Ingestion job failed", extra={"org_id": str(job.org_id), "source_filename": job.payload_filename}
            )

    def _process_retry(self, session, ingestion_jobs: IngestionJobRepository, job: IngestionJob) -> None:
        logger.info("Retry job started", extra={"org_id": str(job.org_id), "document_id": str(job.document_id)})
        try:
            document_repo = DocumentRepository(session)
            document = document_repo.get(job.document_id)
            ingestion_service = IngestionService(
                document_repo, ChunkRepository(session), EmbeddingSettingsRepository(session)
            )
            document = ingestion_service.retry(
                document, should_cancel=lambda: ingestion_jobs.is_cancellation_requested(job.id)
            )
            session.commit()
            ingestion_jobs.update_status(job.id, "indexed", items_processed=1, finished_at=_now())
            session.commit()
            logger.info("Retry job completed", extra={"document_id": str(document.id)})
        except IngestionCancelled:
            session.commit()
            ingestion_jobs.update_status(job.id, "failed", error_message="Cancelled by user.", finished_at=_now())
            session.commit()
            logger.info("Retry job cancelled", extra={"org_id": str(job.org_id), "document_id": str(job.document_id)})
        except Exception as error:
            session.commit()
            ingestion_jobs.update_status(job.id, "failed", error_message=str(error), finished_at=_now())
            session.commit()
            logger.exception("Retry job failed", extra={"org_id": str(job.org_id), "document_id": str(job.document_id)})

    def _process_crawl(self, session, ingestion_jobs: IngestionJobRepository, job: IngestionJob) -> None:
        logger.info(
            "Crawl job started",
            extra={"org_id": str(job.org_id), "seed_url": job.crawl_url, "max_pages": job.crawl_max_pages},
        )
        pages_completed = 0
        try:
            ingestion_service = IngestionService(
                DocumentRepository(session), ChunkRepository(session), EmbeddingSettingsRepository(session)
            )
            crawl_service = WebCrawlService(ingestion_service, WebPageFetcher(user_agent=DEFAULT_WEB_CRAWL_USER_AGENT))

            # Commits after every page -- both the page's document/chunks AND this callback's own
            # per-page status update -- same "durable progress even under a mid-crawl failure or
            # crash" reasoning as _process_upload's on_part_result above.
            def on_page_result(page_url, document, error):
                nonlocal pages_completed
                session.commit()
                if document is not None:
                    pages_completed += 1
                    ingestion_jobs.set_page_status(job.id, page_url, "completed", document.id, None)
                    logger.info("Crawl page completed", extra={"url": page_url, "document_id": str(document.id)})
                else:
                    ingestion_jobs.set_page_status(job.id, page_url, "failed", None, str(error))
                    logger.warning("Crawl page failed", extra={"url": page_url, "error": str(error)})
                session.commit()

            crawl_service.crawl(
                job.org_id,
                job.triggered_by,
                job.crawl_url,
                job.crawl_max_pages,
                category_id=job.category_id,
                scope_prefix=job.crawl_scope_prefix,
                on_page_result=on_page_result,
            )
            ingestion_jobs.update_status(job.id, "indexed", items_processed=pages_completed, finished_at=_now())
            session.commit()
            logger.info("Crawl job completed", extra={"seed_url": job.crawl_url})
        except Exception as error:
            session.commit()
            ingestion_jobs.update_status(
                job.id, "failed", error_message=str(error), items_processed=pages_completed, finished_at=_now()
            )
            session.commit()
            logger.exception("Crawl job failed", extra={"org_id": str(job.org_id), "seed_url": job.crawl_url})
