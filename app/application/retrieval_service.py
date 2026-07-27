from dataclasses import replace
from uuid import UUID

from app.application.rrf import reciprocal_rank_fusion
from app.application.search_settings_service import default_search_settings
from app.domain import error_codes
from app.domain.entities import ScoredChunk
from app.domain.errors import NotFoundError, ValidationError
from app.domain.ports import (
    ChunkRepositoryPort,
    EmbeddingSettingsRepositoryPort,
    LibraryRepositoryPort,
    SearchSettingsRepositoryPort,
)
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.rerank.registry import RerankProviderRegistry


class RetrievalService:
    def __init__(
        self,
        library_repo: LibraryRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
        search_settings_repo: SearchSettingsRepositoryPort,
    ):
        self._libraries = library_repo
        self._chunks = chunk_repo
        self._embedding_settings = embedding_settings_repo
        self._search_settings = search_settings_repo

    def query(self, library_id: UUID, query_text: str, top_k: int) -> list[ScoredChunk]:
        library = self._libraries.get(library_id)
        if library is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")

        embedding_settings = self._embedding_settings.get()
        if embedding_settings is None:
            raise ValidationError(
                error_codes.EMBEDDINGS_NOT_CONFIGURED,
                "Embeddings are not configured. Set an API key in Configuration.",
            )
        search_settings = self._search_settings.get() or default_search_settings()

        provider = EmbeddingProviderRegistry.resolve(
            embedding_settings.provider, embedding_settings.model, embedding_settings.api_key
        )
        query_embedding = provider.embed_query(query_text)

        # Hybrid retrieval is always on (dense + sparse, fused by RRF) — cheap, same Postgres,
        # no extra external calls. Reranking is the opt-in, external-API-call step on top.
        dense = self._chunks.similarity_search(library.id, query_embedding, search_settings.dense_k)
        sparse = self._chunks.sparse_search(library.id, query_text, search_settings.sparse_k)

        chunks_by_id = {chunk.id: chunk for chunk in (*dense, *sparse)}
        fused = reciprocal_rank_fusion(
            [[chunk.id for chunk in dense], [chunk.id for chunk in sparse]],
            k=search_settings.rrf_k,
        )

        limit = search_settings.rerank_candidates if search_settings.rerank_enabled else top_k
        candidates = [
            replace(chunks_by_id[chunk_id], score=fused_score) for chunk_id, fused_score in fused[:limit]
        ]

        if search_settings.rerank_enabled:
            rerank_provider = RerankProviderRegistry.resolve(
                search_settings.rerank_provider, search_settings.rerank_model, embedding_settings.api_key
            )
            reranked = rerank_provider.rerank(query_text, [c.content for c in candidates], top_k)
            candidates = [replace(candidates[index], score=score) for index, score in reranked]

        return candidates[:top_k]
