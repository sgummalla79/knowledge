import hashlib
import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from api.domain import error_codes
from api.domain.entities import Document
from api.domain.errors import IngestionCancelled, ValidationError
from api.domain.ports import ChunkRepositoryPort, DocumentRepositoryPort, EmbeddingSettingsRepositoryPort
from api.infrastructure.chunking.chunker import TextChunker
from api.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from api.infrastructure.parsing.html_parser import HtmlParser
from api.infrastructure.parsing.registry import ParserRegistry

# Documents created via ingest_html() carry this as their file_type — a fixed marker (not derived
# from the source URL, which often has no real file extension, e.g. "/s/articleView?id=...") that
# _resolve_parser uses to route to HtmlParser instead of ParserRegistry's extension lookup.
HTML_SOURCE_FILE_TYPE = "html"

# No tokenizer is bundled (this app supports multiple embedding providers, each with its own
# tokenizer — pinning to one wouldn't be accurate for the others anyway), so token_count is a
# rough chars/4 estimate, the standard rule-of-thumb for English text. Informational only —
# nothing in the retrieval pipeline depends on this being exact.
_CHARS_PER_TOKEN_ESTIMATE = 4

# Every crawled page is classified "article" — the vast majority of web content is, and there's no
# per-URL signal (unlike a file's extension) to classify it any other way.
_DEFAULT_CRAWL_DOCUMENT_TYPE = "article"
# Every file upload is classified "document" — just a starting point, corrigible after the fact via
# PATCH /documents/<id>/metadata. (Previously split further into a "dataset" type for spreadsheet
# extensions, but structured/tabular data doesn't actually belong in this chunk-and-embed pipeline
# at all — it wants exact query access, not similarity search — so that distinction was removed
# rather than kept as a type label with no real tabular capability behind it.)
_DEFAULT_UPLOAD_DOCUMENT_TYPE = "document"

logger = logging.getLogger(__name__)

_html_parser = HtmlParser()


def resolve_file_type(filename: str) -> str:
    """Extracted so callers that already know the true file_type (e.g. PdfSplitIngestionService,
    whose per-part filenames carry a "(part N of M)" display suffix that isn't a real extension)
    can pass it explicitly to ingest() instead of it being silently mis-derived from the filename."""
    return filename.rsplit(".", 1)[-1].lower()


def _estimate_token_count(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)


class IngestionService:
    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
    ):
        self._documents = document_repo
        self._chunks = chunk_repo
        self._embedding_settings = embedding_settings_repo

    def ingest(
        self,
        org_id: UUID,
        owner_id: UUID,
        filename: str,
        file_bytes: bytes,
        category_id: UUID | None = None,
        should_cancel: Callable[[], bool] | None = None,
        file_type: str | None = None,
        split_group_id=None,
        split_part: int | None = None,
        split_total: int | None = None,
    ) -> Document:
        """file_type/split_group_id/split_part/split_total are set explicitly by
        PdfSplitIngestionService when this document is one part of an auto-split oversized PDF —
        file_type must be passed as "pdf" there rather than derived from filename, since a part's
        display filename carries a "(part N of M)" suffix that isn't a real extension. Every other
        caller omits these and gets today's behavior unchanged."""
        settings = self.require_embedding_settings(org_id)

        resolved_file_type = file_type if file_type is not None else resolve_file_type(filename)
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        document = self._documents.create(
            org_id=org_id,
            owner_id=owner_id,
            category_id=category_id,
            title=filename,
            type=_DEFAULT_UPLOAD_DOCUMENT_TYPE,
            file_type=resolved_file_type,
            content_hash=content_hash,
            status="processing",
            # Kept only until this document reaches "indexed" — see
            # DocumentRepository.update_status — so a failed ingestion can be retried without
            # the client re-sending the file.
            raw_file_bytes=file_bytes,
            size_bytes=len(file_bytes),
            split_group_id=split_group_id,
            split_part=split_part,
            split_total=split_total,
        )
        return self._process(document, org_id, file_bytes, settings, should_cancel)

    def ingest_html(
        self,
        org_id: UUID,
        owner_id: UUID,
        url: str,
        html_bytes: bytes,
        category_id: UUID | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Document:
        """Same pipeline as ingest(), for a page fetched from the web (WebCrawlService) instead of
        uploaded. title is the page's URL itself (for display/linking, not extension sniffing) and
        file_type is the fixed HTML_SOURCE_FILE_TYPE marker rather than something derived from the
        URL, which frequently has no real file extension."""
        settings = self.require_embedding_settings(org_id)

        content_hash = hashlib.sha256(html_bytes).hexdigest()
        document = self._documents.create(
            org_id=org_id,
            owner_id=owner_id,
            category_id=category_id,
            title=url,
            type=_DEFAULT_CRAWL_DOCUMENT_TYPE,
            file_type=HTML_SOURCE_FILE_TYPE,
            content_hash=content_hash,
            status="processing",
            raw_file_bytes=html_bytes,
            size_bytes=len(html_bytes),
        )
        return self._process(document, org_id, html_bytes, settings, should_cancel)

    def retry(self, document: Document, should_cancel: Callable[[], bool] | None = None) -> Document:
        """Re-runs the exact same pipeline as ingest(), against an existing document row instead
        of creating a new one, using the raw bytes stored at the original upload. A failed
        ingestion never gets far enough to call ChunkRepository.bulk_create (see _process below —
        chunks are only written after every chunk has embedded successfully), so there's no
        partial-chunk cleanup needed here; retrying just runs the pipeline again from scratch."""
        settings = self.require_embedding_settings(document.org_id)

        file_bytes = self._documents.get_raw_bytes(document.id)
        if file_bytes is None:
            raise ValidationError(
                error_codes.DOCUMENT_NOT_RETRYABLE,
                "No stored file available to retry — this document predates retry support, or "
                "was never actually uploaded with one.",
                field="document_id",
            )
        document = self._documents.update_status(document.id, "processing")
        return self._process(document, document.org_id, file_bytes, settings, should_cancel)

    def require_embedding_settings(self, org_id: UUID):
        settings = self._embedding_settings.get(org_id)
        if settings is None:
            raise ValidationError(
                error_codes.EMBEDDINGS_NOT_CONFIGURED,
                "Embeddings are not configured. Set an API key in Configuration.",
            )
        return settings

    def _resolve_parser(self, document: Document):
        if document.file_type == HTML_SOURCE_FILE_TYPE:
            return _html_parser
        return ParserRegistry.resolve_by_file_type(document.file_type)

    def _process(
        self,
        document: Document,
        org_id: UUID,
        file_bytes: bytes,
        settings,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Document:
        try:
            if should_cancel and should_cancel():
                raise IngestionCancelled("Cancelled by user.")

            parser = self._resolve_parser(document)
            # Postgres text columns reject NUL bytes outright ("A string literal cannot contain
            # NUL (0x00) characters") — some PDFs' extracted text contains them (seen in
            # production). Stripped here, at the boundary where arbitrary file content enters the
            # pipeline, so it can never reach chunks.content regardless of which parser produced it.
            text = parser.parse(file_bytes).replace("\x00", "")

            chunker = TextChunker(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
            pieces = chunker.split(text)
            logger.info(
                "Chunked document", extra={"document_id": str(document.id), "chunk_count": len(pieces)}
            )

            provider = EmbeddingProviderRegistry.resolve(
                settings.provider, settings.model, settings.api_key, settings.base_url
            )
            logger.info(
                "Embedding chunks",
                extra={"provider": settings.provider, "model": settings.model, "chunk_count": len(pieces)},
            )
            vectors = provider.embed_documents(pieces, should_cancel=should_cancel)
            if vectors and len(vectors[0]) != settings.dimensions:
                raise ValidationError(
                    error_codes.EMBEDDING_DIMENSION_MISMATCH,
                    f"Embedding provider '{settings.provider}' model '{settings.model}' produced a "
                    f"{len(vectors[0])}-dimension vector, not the configured {settings.dimensions}.",
                )

            chunks = [
                (ordinal, piece, _estimate_token_count(piece), vector)
                for ordinal, (piece, vector) in enumerate(zip(pieces, vectors))
            ]
            self._chunks.bulk_create(document.id, org_id, settings.id, chunks)

            document = self._documents.update_status(
                document.id, "indexed", indexed_at=datetime.now(timezone.utc), chunk_count=len(chunks)
            )
            logger.info(
                "Ingestion persisted", extra={"document_id": str(document.id), "chunk_count": len(chunks)}
            )
        except IngestionCancelled as error:
            # Distinct from "failed" — this document didn't error out, a user stopped it. Kept
            # (not deleted) and retryable later exactly like a failed document. There's no
            # "cancelled" state in the target document_status enum (processing/indexed/failed/
            # archived) — "failed" is the closest fit, with the cancellation reason preserved in
            # error_message so a caller can still tell the two apart if needed.
            self._documents.update_status(document.id, "failed", error_message=str(error))
            raise
        except Exception as error:
            # No exception logging here — document_service._run_ingestion_job's outer catch is
            # the single place this failure gets logged (with full traceback), to avoid logging
            # the same exception twice at two layers. This except block's only job is cleanup.
            self._documents.update_status(document.id, "failed", error_message=str(error))
            raise

        return document
