from uuid import UUID

from app.domain import error_codes
from app.domain.entities import ScoredChunk
from app.domain.errors import NotFoundError
from app.domain.ports import ChunkRepositoryPort, LibraryRepositoryPort
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


class RetrievalService:
    def __init__(self, library_repo: LibraryRepositoryPort, chunk_repo: ChunkRepositoryPort):
        self._libraries = library_repo
        self._chunks = chunk_repo

    def query(self, library_id: UUID, query_text: str, top_k: int) -> list[ScoredChunk]:
        library = self._libraries.get(library_id)
        if library is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")

        provider = EmbeddingProviderRegistry.resolve(library.embedding_provider, library.embedding_model)
        query_embedding = provider.embed_query(query_text)

        return self._chunks.similarity_search(library.id, query_embedding, top_k)
