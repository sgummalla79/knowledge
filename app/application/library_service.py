import logging
from uuid import UUID

from app.domain import error_codes
from app.domain.entities import Library
from app.domain.errors import NotFoundError
from app.domain.ports import LibraryRepositoryPort

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(self, repository: LibraryRepositoryPort):
        self._repository = repository

    def create_library(self, name: str, description: str | None) -> Library:
        # Embedding provider/model/chunking are global (app.application.embedding_settings_service),
        # not chosen per library — nothing to validate here beyond what the repository enforces
        # (unique name).
        return self._repository.create(name=name, description=description)

    def get_library(self, library_id: UUID) -> Library:
        library = self._repository.get(library_id)
        if library is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        return library

    def list_libraries(self, limit: int, offset: int, sort: str) -> tuple[list[Library], int]:
        return self._repository.list(limit, offset, sort), self._repository.count()

    def delete_library(self, library_id: UUID) -> None:
        if self._repository.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        self._repository.delete(library_id)
        logger.info("Library deleted", extra={"library_id": str(library_id)})
