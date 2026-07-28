from app.application.rerank_choice_validation import validate_rerank_choice
from app.constants import (
    DEFAULT_DENSE_K,
    DEFAULT_RERANK_CANDIDATES,
    DEFAULT_RERANK_ENABLED,
    DEFAULT_RERANK_MODEL,
    DEFAULT_RERANK_PROVIDER,
    DEFAULT_RRF_K,
    DEFAULT_SPARSE_K,
)
from app.domain.entities import SearchSettings
from app.domain.ports import SearchSettingsRepositoryPort


def default_search_settings() -> SearchSettings:
    """Shared by SearchSettingsService.get_status() and RetrievalService — an absent
    `search_settings` row is not an error, it just means these defaults apply."""
    return SearchSettings(
        rerank_enabled=DEFAULT_RERANK_ENABLED,
        rerank_provider=DEFAULT_RERANK_PROVIDER,
        rerank_model=DEFAULT_RERANK_MODEL,
        dense_k=DEFAULT_DENSE_K,
        sparse_k=DEFAULT_SPARSE_K,
        rerank_candidates=DEFAULT_RERANK_CANDIDATES,
        rrf_k=DEFAULT_RRF_K,
        updated_at=None,
    )


class SearchSettingsService:
    """Unlike EmbeddingSettingsService, there's no "not configured" failure state here — an
    absent row just means the DEFAULT_* constants apply, so get_status() always returns usable
    values."""

    def __init__(self, repository: SearchSettingsRepositoryPort):
        self._repository = repository

    def get_status(self) -> SearchSettings:
        return self._repository.get() or default_search_settings()

    def update(
        self,
        rerank_enabled: bool,
        rerank_provider: str,
        rerank_model: str,
        dense_k: int,
        sparse_k: int,
        rerank_candidates: int,
        rrf_k: int,
    ) -> SearchSettings:
        # Only validate rerank_provider/model against SUPPORTED_RERANK_MODELS_BY_PROVIDER when
        # actually turning reranking on — with no supported provider today (see app/constants.py),
        # this keeps updating the other search settings (dense_k, sparse_k, rrf_k, ...) working
        # normally while rerank stays off, rather than blocking every update on an unenforceable
        # provider/model pair.
        if rerank_enabled:
            validate_rerank_choice(rerank_provider, rerank_model)
        return self._repository.upsert(
            rerank_enabled=rerank_enabled,
            rerank_provider=rerank_provider,
            rerank_model=rerank_model,
            dense_k=dense_k,
            sparse_k=sparse_k,
            rerank_candidates=rerank_candidates,
            rrf_k=rrf_k,
        )
