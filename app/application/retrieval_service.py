import logging
from dataclasses import replace
from uuid import UUID

from app.application.rrf import reciprocal_rank_fusion
from app.application.search_settings_service import default_search_settings
from app.domain import error_codes
from app.domain.entities import ScoredChunk, SearchSettings
from app.domain.errors import NotFoundError, ValidationError
from app.domain.ports import (
    ChunkRepositoryPort,
    EmbeddingSettingsRepositoryPort,
    SearchSettingsRepositoryPort,
)
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        library_repo,
        chunk_repo: ChunkRepositoryPort,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
        search_settings_repo: SearchSettingsRepositoryPort,
    ):
        self._libraries = library_repo
        self._chunks = chunk_repo
        self._embedding_settings = embedding_settings_repo
        self._search_settings = search_settings_repo

    def query(
        self,
        library_id: UUID,
        query_text: str,
        top_k: int,
        *,
        query_embedding: list[float] | None = None,
        search_settings: SearchSettings | None = None,
    ) -> list[ScoredChunk]:
        """`query_embedding`/`search_settings` let a caller that's already resolved both (e.g.
        LibraryRouterService, fanning this out across several libraries for one logical query)
        skip the redundant embed call and settings lookup — every other caller leaves them unset
        and gets the original single-library behavior unchanged."""
        logger.info("Query started", extra={"library_id": str(library_id), "top_k": top_k})
        library = self._libraries.get(library_id)
        if library is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")

        if query_embedding is None:
            embedding_settings = self._embedding_settings.get()
            if embedding_settings is None:
                raise ValidationError(
                    error_codes.EMBEDDINGS_NOT_CONFIGURED,
                    "Embeddings are not configured. Set an API key in Configuration.",
                )
            provider = EmbeddingProviderRegistry.resolve(
                embedding_settings.provider,
                embedding_settings.model,
                embedding_settings.api_key,
                embedding_settings.base_url,
            )
            query_embedding = provider.embed_query(query_text)
        if search_settings is None:
            search_settings = self._search_settings.get() or default_search_settings()

        # Hybrid retrieval is always on: dense + sparse, fused by RRF — cheap, same Postgres, no
        # extra external calls.
        dense = self._chunks.similarity_search(library.id, query_embedding, search_settings.dense_k)
        sparse = self._chunks.sparse_search(library.id, query_text, search_settings.sparse_k)
        logger.debug(
            "Retrieval candidates", extra={"dense_count": len(dense), "sparse_count": len(sparse)}
        )

        chunks_by_id = {chunk.id: chunk for chunk in (*dense, *sparse)}
        fused = reciprocal_rank_fusion(
            [[chunk.id for chunk in dense], [chunk.id for chunk in sparse]],
            k=search_settings.rrf_k,
        )

        candidates = [
            replace(chunks_by_id[chunk_id], score=fused_score) for chunk_id, fused_score in fused[:top_k]
        ]
        return candidates
