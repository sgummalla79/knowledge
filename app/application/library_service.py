import logging
from uuid import UUID

from app.domain import error_codes
from app.domain.entities import Library
from app.domain.errors import NotFoundError
from app.domain.ports import EmbeddingSettingsRepositoryPort, LibraryRepositoryPort
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(self, repository: LibraryRepositoryPort, embedding_settings_repo: EmbeddingSettingsRepositoryPort):
        self._repository = repository
        self._embedding_settings = embedding_settings_repo

    def create_library(self, name: str, description: str | None) -> Library:
        # Embedding provider/model/chunking are global (app.application.embedding_settings_service),
        # not chosen per library — nothing to validate here beyond what the repository enforces
        # (unique name).
        library = self._repository.create(name=name, description=description)
        self._sync_description_embedding(library.id, description)
        return library

    def get_library(self, library_id: UUID) -> Library:
        library = self._repository.get(library_id)
        if library is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        return library

    def update_library(self, library_id: UUID, name: str, description: str | None) -> Library:
        if self._repository.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        library = self._repository.update(library_id, name=name, description=description)
        self._sync_description_embedding(library.id, description)
        return library

    def _sync_description_embedding(self, library_id: UUID, description: str | None) -> None:
        """Keeps libraries.description_embedding (used by LibraryRouterService to route a
        library-less query) in sync with the description text. Failures here — no active
        embedding provider, or a live embedding call failing — are swallowed rather than raised:
        library CRUD is a much higher-frequency, more central operation than provider
        configuration, and "no description_embedding" is already a normal excluded-from-routing
        state, not an error state, for the router."""
        if description is None:
            self._repository.set_description_embedding(library_id, None)
            return

        settings = self._embedding_settings.get()
        if settings is None:
            self._repository.set_description_embedding(library_id, None)
            return

        provider = EmbeddingProviderRegistry.resolve(settings.provider, settings.model, settings.api_key, settings.base_url)
        try:
            vector = provider.embed_query(description)
        except Exception:
            logger.warning(
                "Failed to embed library description; excluded from router queries.",
                extra={"library_id": str(library_id)},
                exc_info=True,
            )
            self._repository.set_description_embedding(library_id, None)
            return
        self._repository.set_description_embedding(library_id, vector)

    def list_libraries(self, limit: int, offset: int, sort: str) -> tuple[list[Library], int]:
        return self._repository.list(limit, offset, sort), self._repository.count()

    def delete_library(self, library_id: UUID) -> None:
        if self._repository.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        self._repository.delete(library_id)
        logger.info("Library deleted", extra={"library_id": str(library_id)})
