from uuid import UUID

from app.constants import SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER
from app.domain import error_codes
from app.domain.entities import Library
from app.domain.errors import NotFoundError, ValidationError
from app.domain.ports import LibraryRepositoryPort


class LibraryService:
    def __init__(self, repository: LibraryRepositoryPort):
        self._repository = repository

    def create_library(
        self,
        name: str,
        description: str | None,
        embedding_provider: str,
        embedding_model: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> Library:
        # Checked here, at creation time, rather than only surfacing later as a failed
        # ingestion job when the first document is uploaded.
        if chunk_overlap >= chunk_size:
            raise ValidationError(
                error_codes.VALIDATION_ERROR,
                "chunk_overlap must be smaller than chunk_size.",
                field="chunk_overlap",
            )

        supported_models = SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER.get(embedding_provider)
        if supported_models is None:
            raise ValidationError(
                error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
                f"Unsupported embedding provider '{embedding_provider}'.",
                field="embedding_provider",
            )
        if embedding_model not in supported_models:
            raise ValidationError(
                error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
                f"Unsupported embedding model '{embedding_model}' for provider '{embedding_provider}'.",
                field="embedding_model",
            )

        return self._repository.create(
            name=name,
            description=description,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

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
