import logging
from dataclasses import replace
from uuid import UUID

from api.application.rrf import reciprocal_rank_fusion
from api.constants import DEFAULT_DENSE_K, DEFAULT_RRF_K, DEFAULT_SPARSE_K
from api.domain import error_codes
from api.domain.entities import ScoredChunk
from api.domain.errors import ValidationError
from api.domain.ports import ChunkRepositoryPort, EmbeddingSettingsRepositoryPort
from api.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self, chunk_repo: ChunkRepositoryPort, embedding_settings_repo: EmbeddingSettingsRepositoryPort):
        self._chunks = chunk_repo
        self._embedding_settings = embedding_settings_repo

    def query(
        self,
        org_id: UUID,
        query_text: str,
        top_k: int,
        *,
        category_id: UUID | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[ScoredChunk]:
        """`query_embedding` lets a caller that's already embedded the query once (e.g.
        CategoryRouterService, fanning this out across several categories for one logical query)
        skip the redundant embed call — every other caller leaves it unset and gets it embedded
        here. `category_id` narrows retrieval to one category within the org (CategoryRouterService
        always sets it, per matched category); omitted, retrieval spans the whole org."""
        logger.info("Query started", extra={"org_id": str(org_id), "top_k": top_k})

        if query_embedding is None:
            embedding_settings = self._embedding_settings.get(org_id)
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

        # Hybrid retrieval is always on: dense + sparse, fused by RRF — cheap, same Postgres, no
        # extra external calls.
        dense = self._chunks.similarity_search(org_id, query_embedding, DEFAULT_DENSE_K, category_id)
        sparse = self._chunks.sparse_search(org_id, query_text, DEFAULT_SPARSE_K, category_id)
        logger.debug(
            "Retrieval candidates", extra={"dense_count": len(dense), "sparse_count": len(sparse)}
        )

        chunks_by_id = {chunk.id: chunk for chunk in (*dense, *sparse)}
        fused = reciprocal_rank_fusion(
            [[chunk.id for chunk in dense], [chunk.id for chunk in sparse]],
            k=DEFAULT_RRF_K,
        )

        candidates = [
            replace(chunks_by_id[chunk_id], score=fused_score) for chunk_id, fused_score in fused[:top_k]
        ]
        return candidates
