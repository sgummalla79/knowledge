import hashlib
from datetime import datetime, timezone

from app.domain.entities import Library
from app.domain.ports import ChunkRepositoryPort, DocumentRepositoryPort, LibraryRepositoryPort
from app.infrastructure.chunking.chunker import TextChunker
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.parsing.registry import ParserRegistry


class IngestionService:
    def __init__(
        self,
        library_repo: LibraryRepositoryPort,
        document_repo: DocumentRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
    ):
        self._libraries = library_repo
        self._documents = document_repo
        self._chunks = chunk_repo

    def ingest(self, library: Library, filename: str, file_bytes: bytes):
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        document = self._documents.create(
            library_id=library.id,
            source_filename=filename,
            file_type=filename.rsplit(".", 1)[-1].lower(),
            content_hash=content_hash,
            status="processing",
        )

        try:
            parser = ParserRegistry.resolve(filename)
            text = parser.parse(file_bytes)

            chunker = TextChunker(chunk_size=library.chunk_size, chunk_overlap=library.chunk_overlap)
            pieces = chunker.split(text)

            provider = EmbeddingProviderRegistry.resolve(
                library.embedding_provider, library.embedding_model
            )
            vectors = provider.embed_documents(pieces)

            chunks = [(index, piece, vector) for index, (piece, vector) in enumerate(zip(pieces, vectors))]
            self._chunks.bulk_create(document.id, library.id, chunks)

            document = self._documents.update_status(
                document.id, "completed", ingested_at=datetime.now(timezone.utc)
            )
            self._libraries.increment_counts(library.id, document_delta=1, chunk_delta=len(chunks))
        except Exception:
            self._documents.update_status(document.id, "failed")
            raise

        return document
