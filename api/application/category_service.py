import logging
from uuid import UUID

from api.application.slugify import slugify
from api.domain import error_codes
from api.domain.entities import Category
from api.domain.errors import AuthenticationError, NotFoundError, ValidationError
from api.domain.ports import CategoryRepositoryPort, DocumentRepositoryPort, EmbeddingSettingsRepositoryPort, IdentityRepositoryPort
from api.infrastructure.auth.passwords import verify_password
from api.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class CategoryService:
    def __init__(
        self,
        repository: CategoryRepositoryPort,
        embedding_settings_repo: EmbeddingSettingsRepositoryPort,
        document_repo: DocumentRepositoryPort | None = None,
        identity_repo: IdentityRepositoryPort | None = None,
    ):
        self._repository = repository
        self._embedding_settings = embedding_settings_repo
        # Optional: only delete_category(cascade=True) needs these, to find/delete the category's
        # documents and to re-verify the acting identity's password first.
        self._documents = document_repo
        self._identities = identity_repo

    def create_category(
        self, org_id: UUID, name: str, description: str | None, parent_id: UUID | None = None
    ) -> Category:
        # Embedding provider/model/chunking are global per org (api.application.
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

    def delete_category(
        self,
        org_id: UUID,
        category_id: UUID,
        acting_identity_id: UUID | None = None,
        cascade: bool = False,
        current_password: str | None = None,
    ) -> int:
        """Default (cascade=False) is a plain unlink, exactly as before -- documents currently in
        this category just become uncategorized (documents.category_id ON DELETE SET NULL).
        cascade=True additionally, permanently deletes every one of those documents; their chunks
        cascade-delete at the DB level (chunks.document_id ON DELETE CASCADE), same guarantee
        DocumentService.delete_document already relies on. Requires the acting identity's current
        password first -- same re-verification AuthService.change_username /
        OrgMembershipService.change_organization_name already use for other
        destructive/security-sensitive actions, so a hijacked session can't silently bulk-delete
        content just by holding the cookie. Returns how many documents were deleted (0 for a plain
        unlink)."""
        self.get_category(org_id, category_id)

        deleted_count = 0
        if cascade:
            if not current_password:
                raise ValidationError(
                    error_codes.VALIDATION_ERROR,
                    "Current password is required to permanently delete documents.",
                    field="current_password",
                )
            identity = self._identities.get_by_id(acting_identity_id) if acting_identity_id else None
            if identity is None or not verify_password(current_password, identity.password_hash):
                raise AuthenticationError("Incorrect password.", code=error_codes.INCORRECT_PASSWORD)

            deleted_count = self._documents.count_for_org(org_id, category_id=category_id)
            if deleted_count:
                documents = self._documents.list_for_org(
                    org_id, deleted_count, 0, "created_at", category_id=category_id
                )
                for document in documents:
                    self._documents.delete(document.id)

        self._repository.delete(category_id)
        logger.info(
            "Category deleted",
            extra={
                "org_id": str(org_id),
                "category_id": str(category_id),
                "cascade": cascade,
                "documents_deleted": deleted_count,
            },
        )
        return deleted_count

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
