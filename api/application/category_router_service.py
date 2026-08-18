import logging
from dataclasses import replace
from uuid import UUID

from api.application.retrieval_service import RetrievalService
from api.application.rrf import reciprocal_rank_fusion
from api.constants import DEFAULT_RRF_K, DEFAULT_ROUTER_MIN_SIMILARITY, DEFAULT_ROUTER_TOP_N
from api.domain import error_codes
from api.domain.entities import RoutedScoredChunk
from api.domain.errors import ValidationError
from api.domain.ports import CategoryRepositoryPort, EmbeddingSettingsRepositoryPort
from api.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class CategoryRouterService:
    """Answers a query with no category_id: embeds the query once, ranks categories by cosine
    similarity between that embedding and each category's cached description_embedding, retrieves
    from every category that clears DEFAULT_ROUTER_MIN_SIMILARITY (up to DEFAULT_ROUTER_TOP_N),
    and merges the per-category results into one ranked list via RRF — the same fusion
    RetrievalService already uses for dense+sparse, applied a second time across categories
    instead of across retrieval modes. RRF only depends on rank position, not raw score
    magnitude, so this sidesteps "scores from different categories aren't on the same scale" the
    way a naive concatenate-and-sort merge would not.

    Direct successor of the pre-multi-tenant LibraryRouterService — same algorithm, categories in
    place of libraries (see docs/DATA_MODEL.md).
    """

    def __init__(
        self,
        category_repo: CategoryRepositoryPort,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
        retrieval_service: RetrievalService,
    ):
        self._categories = category_repo
        self._embedding_settings = embedding_settings_repo
        self._retrieval = retrieval_service

    def query(self, org_id: UUID, query_text: str, top_k: int) -> list[RoutedScoredChunk]:
        logger.info("Router query started", extra={"org_id": str(org_id), "top_k": top_k})
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

        candidates = self._categories.search_by_description_similarity(
            org_id, query_embedding, top_n=DEFAULT_ROUTER_TOP_N, min_similarity=DEFAULT_ROUTER_MIN_SIMILARITY
        )
        if not candidates:
            # No category's description cleared the threshold — a valid empty result, not an
            # error (mirrors search_by_description_similarity's own "no match" being unremarkable).
            return []

        per_category = [
            (
                category,
                self._retrieval.query(org_id, query_text, top_k, category_id=category.id, query_embedding=query_embedding),
            )
            for category, _similarity in candidates
        ]
        return self._merge(per_category, top_k)

    def _merge(self, per_category, top_k: int) -> list[RoutedScoredChunk]:
        chunks_by_id = {chunk.id: (category, chunk) for category, chunks in per_category for chunk in chunks}
        fused = reciprocal_rank_fusion(
            [[chunk.id for chunk in chunks] for _category, chunks in per_category], k=DEFAULT_RRF_K
        )
        return [
            RoutedScoredChunk(
                category_id=chunks_by_id[chunk_id][0].id,
                category_name=chunks_by_id[chunk_id][0].name,
                chunk=replace(chunks_by_id[chunk_id][1], score=fused_score),
            )
            for chunk_id, fused_score in fused[:top_k]
        ]
