from dataclasses import dataclass
from datetime import datetime

from app.application.embedding_choice_validation import validate_embedding_choice
from app.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.domain.ports import EmbeddingSettingsRepositoryPort


@dataclass(frozen=True)
class EmbeddingSettingsStatus:
    provider: str | None
    model: str | None
    configured: bool
    base_url: str | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None


class EmbeddingSettingsService:
    def __init__(self, repository: EmbeddingSettingsRepositoryPort):
        self._repository = repository

    def get_status(self) -> EmbeddingSettingsStatus:
        settings = self._repository.get()
        if settings is None:
            return EmbeddingSettingsStatus(
                provider=None,
                model=None,
                configured=False,
                base_url=None,
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                updated_at=None,
            )
        return EmbeddingSettingsStatus(
            provider=settings.provider,
            model=settings.model,
            configured=True,
            base_url=settings.base_url,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            updated_at=settings.updated_at,
        )

    def update(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        chunk_size: int,
        chunk_overlap: int,
        base_url: str | None = None,
    ) -> EmbeddingSettingsStatus:
        validate_embedding_choice(provider, model, api_key)
        # Checked here, at save time, rather than only surfacing later as a failed ingestion job
        # when the first document is uploaded.
        if chunk_overlap >= chunk_size:
            raise ValidationError(
                error_codes.VALIDATION_ERROR,
                "chunk_overlap must be smaller than chunk_size.",
                field="chunk_overlap",
            )
        settings = self._repository.upsert(provider, model, api_key, chunk_size, chunk_overlap, base_url)
        return EmbeddingSettingsStatus(
            provider=settings.provider,
            model=settings.model,
            configured=True,
            base_url=settings.base_url,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            updated_at=settings.updated_at,
        )

    def clear(self) -> EmbeddingSettingsStatus:
        self._repository.clear()
        return EmbeddingSettingsStatus(
            provider=None,
            model=None,
            configured=False,
            base_url=None,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
            updated_at=None,
        )
