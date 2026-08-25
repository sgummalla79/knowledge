import logging
from typing import Callable
from uuid import UUID, uuid4

from api.application.ingestion_service import IngestionService, resolve_file_type
from api.constants import MAX_UPLOAD_MB
from api.domain import error_codes
from api.domain.entities import Document
from api.domain.errors import IngestionCancelled, ValidationError
from api.infrastructure.parsing.pdf_splitter import PdfSplitter
from api.infrastructure.storage.upload_storage import UploadStorage

logger = logging.getLogger(__name__)

PDF_FILE_TYPE = "pdf"

OnPartResult = Callable[[int, int, Document | None, Exception | None], None]


class PdfSplitIngestionService:
    """Wraps IngestionService so an oversized PDF is split into multiple parts (PdfSplitter)
    before ingestion instead of being rejected outright. Non-PDF files and PDFs at or under the
    split threshold pass straight through to IngestionService.ingest() unchanged, with exceptions
    propagating exactly as before — the split path is additive, never a behavior change for the
    single-document case. Only once a PDF actually splits into multiple parts does per-part
    try/except/callback handling kick in, mirroring WebCrawlService.crawl's per-page loop: a
    failure in one part is reported via on_part_result and does not stop the remaining parts."""

    def __init__(
        self, ingestion_service: IngestionService, storage: UploadStorage, splitter: PdfSplitter | None = None
    ):
        self._ingestion_service = ingestion_service
        self._storage = storage
        self._splitter = splitter or PdfSplitter()

    def ingest(
        self,
        org_id: UUID,
        owner_id: UUID,
        job_id: UUID,
        filename: str,
        source_path: str,
        category_id: UUID | None = None,
        should_cancel: Callable[[], bool] | None = None,
        on_part_result: OnPartResult | None = None,
    ) -> None:
        """source_path is the whole originally-uploaded file (ingestion_jobs.payload_path), read
        here but never moved/deleted by this method — IngestionService.ingest() takes ownership of
        it directly for the non-split cases below; for a real split, each part gets its own
        temporary file (job_id names that file's directory) that IngestionService.ingest() takes
        ownership of instead, leaving source_path itself untouched throughout. Either way, the
        caller (the worker) is responsible for reclaiming source_path once this call returns."""
        file_type = resolve_file_type(filename)
        size_bytes = self._storage.size(source_path)

        if file_type != PDF_FILE_TYPE:
            # MAX_CONTENT_LENGTH (MAX_REQUEST_BODY_MB) now admits requests well over MAX_UPLOAD_MB
            # at the WSGI layer to let oversized PDFs reach PdfSplitter — a non-PDF file must still
            # be capped at the original per-file limit, just enforced here instead of by Werkzeug.
            if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
                raise ValidationError(
                    error_codes.FILE_TOO_LARGE,
                    f"File exceeds the {MAX_UPLOAD_MB}MB size limit.",
                    field="file",
                )
            document = self._ingestion_service.ingest(
                org_id, owner_id, filename, source_path, category_id=category_id, should_cancel=should_cancel
            )
            if on_part_result:
                on_part_result(1, 1, document, None)
            return

        settings = self._ingestion_service.require_embedding_settings(org_id)
        resolved_path = self._storage.resolve(source_path)
        plan = self._splitter.plan_for(resolved_path, size_bytes, settings.chunk_size, settings.chunk_overlap)

        if plan is None:
            document = self._ingestion_service.ingest(
                org_id,
                owner_id,
                filename,
                source_path,
                category_id=category_id,
                should_cancel=should_cancel,
                file_type=PDF_FILE_TYPE,
            )
            if on_part_result:
                on_part_result(1, 1, document, None)
            return

        # iter_parts() yields one part at a time rather than every part up front (see its own
        # docstring) -- each part_bytes is only ever referenced by this loop iteration, so it's
        # free to be garbage-collected once its own file is written, instead of every part staying
        # alive in memory for the whole job.
        split_group_id = uuid4()
        total = plan.total_parts
        for index, part_bytes in enumerate(self._splitter.iter_parts(resolved_path, plan), start=1):
            if should_cancel and should_cancel():
                raise IngestionCancelled("Cancelled by user.")

            part_filename = f"{filename} (part {index} of {total})"
            part_path = self._storage.path_for_part(org_id, job_id, index)
            self._storage.save_bytes(part_path, part_bytes)
            del part_bytes
            try:
                document = self._ingestion_service.ingest(
                    org_id,
                    owner_id,
                    part_filename,
                    part_path,
                    category_id=category_id,
                    should_cancel=should_cancel,
                    file_type=PDF_FILE_TYPE,
                    split_group_id=split_group_id,
                    split_part=index,
                    split_total=total,
                )
                if on_part_result:
                    on_part_result(index, total, document, None)
            except IngestionCancelled:
                raise
            except Exception as error:
                logger.warning(
                    "Failed to ingest PDF split part",
                    extra={
                        "org_id": str(org_id),
                        "source_filename": part_filename,
                        "split_part": index,
                        "split_total": total,
                        "error": str(error),
                    },
                )
                if on_part_result:
                    on_part_result(index, total, None, error)
