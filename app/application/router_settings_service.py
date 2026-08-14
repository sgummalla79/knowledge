from app.constants import DEFAULT_ROUTER_MIN_SIMILARITY, DEFAULT_ROUTER_TOP_N
from app.domain.entities import RouterSettings
from app.domain.ports import RouterSettingsRepositoryPort


def default_router_settings() -> RouterSettings:
    """Shared by RouterSettingsService.get_status() and LibraryRouterService — an absent
    `router_settings` row is not an error, it just means these defaults apply."""
    return RouterSettings(
        top_n=DEFAULT_ROUTER_TOP_N,
        min_similarity=DEFAULT_ROUTER_MIN_SIMILARITY,
        updated_at=None,
    )


class RouterSettingsService:
    """Unlike EmbeddingProviderConfigService, there's no "not configured" failure state here — an
    absent row just means the DEFAULT_* constants apply, so get_status() always returns usable
    values."""

    def __init__(self, repository: RouterSettingsRepositoryPort):
        self._repository = repository

    def get_status(self) -> RouterSettings:
        return self._repository.get() or default_router_settings()

    def update(self, top_n: int, min_similarity: float) -> RouterSettings:
        return self._repository.upsert(top_n=top_n, min_similarity=min_similarity)
