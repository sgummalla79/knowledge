import logging
from uuid import UUID

from app.application.slugify import slugify
from app.domain import error_codes
from app.domain.entities import Category
from app.domain.errors import NotFoundError
from app.domain.ports import CategoryRepositoryPort, EmbeddingSettingsRepositoryPort
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class CategoryService:
    def __init__(self, repository: CategoryRepositoryPort, embedding_settings_repo: EmbeddingSettingsRepositoryPort):
        self._repository = repository
        self._embedding_settings = embedding_settings_repo

    def create_category(
        self, org_id: UUID, name: str, description: str | None, parent_id: UUID | None = None
    ) -> Category:
        # Embedding provider/model/chunking are global per org (app.application.
        # embedding_provider_settings_service), not chosen per category — nothing to validate here
        # beyond what the repository enforces (unique slug within the org).
        slug = slugify(name)
        category = self._repository.create(org_id, name=name, slug=slug, description=description, parent_id=parent_id)
        self._sync_description_embedding(org_id, category.id, description)
        return category

    def get_category(self, org_id: UUID, category_id: UUID) -> Category:
        category = self._repository.get(category_id)
        if category is None or category.org_id != org_id:
            raise NotFoundError(error_codes.CATEGORY_NOT_FOUND, "Category not found.")
        return category

    def update_category(self, org_id: UUID, category_id: UUID, name: str, description: str | None) -> Category:
        self.get_category(org_id, category_id)
        category = self._repository.update(category_id, name=name, description=description)
        self._sync_description_embedding(org_id, category.id, description)
        return category

    def list_categories(self, org_id: UUID) -> list[Category]:
        return self._repository.list_by_org(org_id)

    def delete_category(self, org_id: UUID, category_id: UUID) -> None:
        self.get_category(org_id, category_id)
        self._repository.delete(category_id)
        logger.info("Category deleted", extra={"org_id": str(org_id), "category_id": str(category_id)})

    def _sync_description_embedding(self, org_id: UUID, category_id: UUID, description: str | None) -> None:
        """Keeps categories.description_embedding (used by CategoryRouterService to route a
        category-less query) in sync with the description text. Failures here — no active
        embedding provider, or a live embedding call failing — are swallowed rather than raised:
        category CRUD is a much higher-frequency, more central operation than provider
        configuration, and "no description_embedding" is already a normal excluded-from-routing
        state, not an error state, for the router."""
        if description is None:
            self._repository.set_description_embedding(category_id, None)
            return

        settings = self._embedding_settings.get(org_id)
        if settings is None:
            self._repository.set_description_embedding(category_id, None)
            return

        provider = EmbeddingProviderRegistry.resolve(settings.provider, settings.model, settings.api_key, settings.base_url)
        try:
            vector = provider.embed_query(description)
        except Exception:
            logger.warning(
                "Failed to embed category description; excluded from router queries.",
                extra={"category_id": str(category_id)},
                exc_info=True,
            )
            self._repository.set_description_embedding(category_id, None)
            return
        self._repository.set_description_embedding(category_id, vector)
