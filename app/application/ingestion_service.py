import hashlib
import logging
from datetime import datetime, timezone

from app.domain import error_codes
from app.domain.entities import Document, Library
from app.domain.errors import ValidationError
from app.domain.ports import ChunkRepositoryPort, DocumentRepositoryPort, EmbeddingSettingsRepositoryPort, LibraryRepositoryPort
from app.infrastructure.chunking.chunker import TextChunker
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.parsing.registry import ParserRegistry

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        library_repo: LibraryRepositoryPort,
        document_repo: DocumentRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
    ):
        self._libraries = library_repo
        self._documents = document_repo
        self._chunks = chunk_repo
        self._embedding_settings = embedding_settings_repo

    def ingest(self, library: Library, filename: str, file_bytes: bytes) -> Document:
        settings = self._require_embedding_settings()

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        document = self._documents.create(
            library_id=library.id,
            source_filename=filename,
            file_type=filename.rsplit(".", 1)[-1].lower(),
            content_hash=content_hash,
            status="processing",
            # Kept only until this document reaches "completed" — see
            # DocumentRepository.update_status — so a failed ingestion can be retried without
            # the client re-sending the file.
            raw_file_bytes=file_bytes,
            size_bytes=len(file_bytes),
        )
        return self._process(document, library, file_bytes, settings)

    def retry(self, document: Document, library: Library) -> Document:
        """Re-runs the exact same pipeline as ingest(), against an existing document row instead
        of creating a new one, using the raw bytes stored at the original upload. A failed
        ingestion never gets far enough to call ChunkRepository.bulk_create (see _process below —
        chunks are only written after every chunk has embedded successfully), so there's no
        partial-chunk cleanup needed here; retrying just runs the pipeline again from scratch."""
        settings = self._require_embedding_settings()

        file_bytes = self._documents.get_raw_bytes(document.id)
        if file_bytes is None:
            raise ValidationError(
                error_codes.DOCUMENT_NOT_RETRYABLE,
                "No stored file available to retry — this document predates retry support, or "
                "was never actually uploaded with one.",
                field="document_id",
            )
        document = self._documents.update_status(document.id, "processing")
        return self._process(document, library, file_bytes, settings)

    def _require_embedding_settings(self):
        settings = self._embedding_settings.get()
        if settings is None:
            raise ValidationError(
                error_codes.EMBEDDINGS_NOT_CONFIGURED,
                "Embeddings are not configured. Set an API key in Configuration.",
            )
        return settings

    def _process(self, document: Document, library: Library, file_bytes: bytes, settings) -> Document:
        try:
            parser = ParserRegistry.resolve(document.source_filename)
            text = parser.parse(file_bytes)

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
            vectors = provider.embed_documents(pieces)
            if vectors and len(vectors[0]) != settings.dimensions:
                raise ValidationError(
                    error_codes.EMBEDDING_DIMENSION_MISMATCH,
                    f"Embedding provider '{settings.provider}' model '{settings.model}' produced a "
                    f"{len(vectors[0])}-dimension vector, not the configured {settings.dimensions}.",
                )

            chunks = [(index, piece, vector) for index, (piece, vector) in enumerate(zip(pieces, vectors))]
            self._chunks.bulk_create(document.id, library.id, chunks)

            document = self._documents.update_status(
                document.id, "completed", ingested_at=datetime.now(timezone.utc), chunk_count=len(chunks)
            )
            self._libraries.increment_counts(library.id, document_delta=1, chunk_delta=len(chunks))
            logger.info(
                "Ingestion persisted", extra={"document_id": str(document.id), "chunk_count": len(chunks)}
            )
        except Exception as error:
            # No exception logging here — document_service._run_ingestion_job's outer catch is
            # the single place this failure gets logged (with full traceback), to avoid logging
            # the same exception twice at two layers. This except block's only job is cleanup.
            self._documents.update_status(document.id, "failed", error_message=str(error))
            raise

        return document
