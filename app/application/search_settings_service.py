from app.constants import DEFAULT_DENSE_K, DEFAULT_RRF_K, DEFAULT_SPARSE_K
from app.domain.entities import SearchSettings
from app.domain.ports import SearchSettingsRepositoryPort


def default_search_settings() -> SearchSettings:
    """Shared by SearchSettingsService.get_status() and RetrievalService — an absent
    `search_settings` row is not an error, it just means these defaults apply."""
    return SearchSettings(
        dense_k=DEFAULT_DENSE_K,
        sparse_k=DEFAULT_SPARSE_K,
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

    def update(self, dense_k: int, sparse_k: int, rrf_k: int) -> SearchSettings:
        return self._repository.upsert(dense_k=dense_k, sparse_k=sparse_k, rrf_k=rrf_k)
