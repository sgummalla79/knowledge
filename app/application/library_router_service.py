import logging
from dataclasses import replace

from app.application.retrieval_service import RetrievalService
from app.application.router_settings_service import default_router_settings
from app.application.rrf import reciprocal_rank_fusion
from app.application.search_settings_service import default_search_settings
from app.domain import error_codes
from app.domain.entities import RoutedScoredChunk
from app.domain.errors import ValidationError
from app.domain.ports import (
    EmbeddingSettingsRepositoryPort,
    RouterSettingsRepositoryPort,
    SearchSettingsRepositoryPort,
)
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class LibraryRouterService:
    """Answers a query with no library_id: embeds the query once, ranks libraries by cosine
    similarity between that embedding and each library's cached description_embedding (see
    LibraryService._sync_description_embedding), retrieves from every library that clears
    router_settings.min_similarity (up to top_n), and merges the per-library results into one
    ranked list via RRF — the same fusion RetrievalService already uses for dense+sparse, applied
    a second time across libraries instead of across retrieval modes. RRF only depends on rank
    position, not raw score magnitude, so this sidesteps "scores from different libraries aren't
    on the same scale" the way a naive concatenate-and-sort merge would not.
    """

    def __init__(
        self,
        library_repo,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
        router_settings_repo: RouterSettingsRepositoryPort,
        search_settings_repo: SearchSettingsRepositoryPort,
        retrieval_service: RetrievalService,
    ):
        self._libraries = library_repo
        self._embedding_settings = embedding_settings_repo
        self._router_settings = router_settings_repo
        self._search_settings = search_settings_repo
        self._retrieval = retrieval_service

    def query(self, query_text: str, top_k: int) -> list[RoutedScoredChunk]:
        logger.info("Router query started", extra={"top_k": top_k})
        embedding_settings = self._embedding_settings.get()
        if embedding_settings is None:
            raise ValidationError(
                error_codes.EMBEDDINGS_NOT_CONFIGURED,
                "Embeddings are not configured. Set an API key in Configuration.",
            )

        router_settings = self._router_settings.get() or default_router_settings()
        search_settings = self._search_settings.get() or default_search_settings()

        provider = EmbeddingProviderRegistry.resolve(
            embedding_settings.provider,
            embedding_settings.model,
            embedding_settings.api_key,
            embedding_settings.base_url,
        )
        query_embedding = provider.embed_query(query_text)

        candidates = self._libraries.search_by_description_similarity(
            query_embedding, top_n=router_settings.top_n, min_similarity=router_settings.min_similarity
        )
        if not candidates:
            # No library's description cleared the threshold — a valid empty result, not an
            # error (mirrors search_by_description_similarity's own "no match" being unremarkable).
            return []

        per_library = [
            (
                library,
                self._retrieval.query(
                    library.id, query_text, top_k, query_embedding=query_embedding, search_settings=search_settings
                ),
            )
            for library, _similarity in candidates
        ]
        return self._merge(per_library, top_k, search_settings.rrf_k)

    def _merge(self, per_library, top_k: int, rrf_k: int) -> list[RoutedScoredChunk]:
        chunks_by_id = {chunk.id: (library, chunk) for library, chunks in per_library for chunk in chunks}
        fused = reciprocal_rank_fusion(
            [[chunk.id for chunk in chunks] for _library, chunks in per_library], k=rrf_k
        )
        return [
            RoutedScoredChunk(
                category_id=chunks_by_id[chunk_id][0].id,
                category_name=chunks_by_id[chunk_id][0].name,
                chunk=replace(chunks_by_id[chunk_id][1], score=fused_score),
            )
            for chunk_id, fused_score in fused[:top_k]
        ]
