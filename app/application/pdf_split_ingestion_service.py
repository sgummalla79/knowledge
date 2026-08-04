import logging
from typing import Callable
from uuid import uuid4

from app.application.ingestion_service import IngestionService, resolve_file_type
from app.constants import MAX_UPLOAD_MB
from app.domain import error_codes
from app.domain.entities import Document, Library
from app.domain.errors import IngestionCancelled, ValidationError
from app.infrastructure.parsing.pdf_splitter import PdfSplitter

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

    def __init__(self, ingestion_service: IngestionService, splitter: PdfSplitter | None = None):
        self._ingestion_service = ingestion_service
        self._splitter = splitter or PdfSplitter()

    def ingest(
        self,
        library: Library,
        filename: str,
        file_bytes: bytes,
        should_cancel: Callable[[], bool] | None = None,
        on_part_result: OnPartResult | None = None,
    ) -> None:
        file_type = resolve_file_type(filename)

        if file_type != PDF_FILE_TYPE:
            # MAX_CONTENT_LENGTH (MAX_REQUEST_BODY_MB) now admits requests well over MAX_UPLOAD_MB
            # at the WSGI layer to let oversized PDFs reach PdfSplitter — a non-PDF file must still
            # be capped at the original per-file limit, just enforced here instead of by Werkzeug.
            if len(file_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
                raise ValidationError(
                    error_codes.FILE_TOO_LARGE,
                    f"File exceeds the {MAX_UPLOAD_MB}MB size limit.",
                    field="file",
                )
            document = self._ingestion_service.ingest(library, filename, file_bytes, should_cancel=should_cancel)
            if on_part_result:
                on_part_result(1, 1, document, None)
            return

        settings = self._ingestion_service.require_embedding_settings()
        parts = self._splitter.split(file_bytes, settings.chunk_size, settings.chunk_overlap)

        if len(parts) == 1:
            document = self._ingestion_service.ingest(
                library, filename, parts[0], should_cancel=should_cancel, file_type=PDF_FILE_TYPE
            )
            if on_part_result:
                on_part_result(1, 1, document, None)
            return

        split_group_id = uuid4()
        total = len(parts)
        for index, part_bytes in enumerate(parts, start=1):
            if should_cancel and should_cancel():
                raise IngestionCancelled("Cancelled by user.")

            part_filename = f"{filename} (part {index} of {total})"
            try:
                document = self._ingestion_service.ingest(
                    library,
                    part_filename,
                    part_bytes,
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
                        "library_id": str(library.id),
                        "source_filename": part_filename,
                        "split_part": index,
                        "split_total": total,
                        "error": str(error),
                    },
                )
                if on_part_result:
                    on_part_result(index, total, None, error)
