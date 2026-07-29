from dataclasses import dataclass
from datetime import datetime

from app.application.embedding_choice_validation import validate_embedding_choice
from app.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.domain.ports import (
    ChunkRepositoryPort,
    EmbeddingProviderSettingsRepositoryPort,
    EmbeddingSettingsRepositoryPort,
)
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


@dataclass(frozen=True)
class EmbeddingSettingsStatus:
    provider: str | None
    model: str | None
    configured: bool
    base_url: str | None
    dimensions: int | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None


class EmbeddingSettingsService:
    def __init__(
        self,
        repository: EmbeddingSettingsRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        provider_settings_repo: EmbeddingProviderSettingsRepositoryPort,
    ):
        self._repository = repository
        self._chunks = chunk_repo
        self._provider_settings = provider_settings_repo

    def get_status(self) -> EmbeddingSettingsStatus:
        settings = self._repository.get()
        if settings is None:
            return EmbeddingSettingsStatus(
                provider=None,
                model=None,
                configured=False,
                base_url=None,
                dimensions=None,
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                updated_at=None,
            )
        return EmbeddingSettingsStatus(
            provider=settings.provider,
            model=settings.model,
            configured=True,
            base_url=settings.base_url,
            dimensions=settings.dimensions,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            updated_at=settings.updated_at,
        )

    def update(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
        base_url: str | None = None,
    ) -> EmbeddingSettingsStatus:
        validate_embedding_choice(
            provider, model, api_key, base_url, dimensions, self._provider_settings.get_enabled_providers()
        )
        # Checked here, at save time, rather than only surfacing later as a failed ingestion job
        # when the first document is uploaded.
        if chunk_overlap >= chunk_size:
            raise ValidationError(
                error_codes.VALIDATION_ERROR,
                "chunk_overlap must be smaller than chunk_size.",
                field="chunk_overlap",
            )

        existing = self._repository.get()
        model_identity_changed = existing is not None and (
            existing.provider != provider
            or existing.model != model
            or existing.base_url != base_url
            or existing.dimensions != dimensions
        )
        if model_identity_changed and self._chunks.count_all() > 0:
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LOCKED,
                "Cannot change the embedding provider/model/base_url/dimensions while documents "
                "exist — delete all documents first, since embeddings from different models are "
                "not comparable.",
                field="provider",
            )

        # A brand-new configuration, or any change to provider/model/base_url/dimensions: verify
        # the endpoint is reachable and actually produces vectors of the declared length before
        # persisting, so a bad credential or wrong dimensions surfaces here as a clear error
        # instead of a cryptic failure during ingestion.
        if existing is None or model_identity_changed:
            provider_instance = EmbeddingProviderRegistry.resolve(provider, model, api_key, base_url)
            try:
                vector = provider_instance.embed_query("connection test")
            except Exception as error:
                raise ValidationError(
                    error_codes.VALIDATION_ERROR,
                    f"Could not verify embedding provider '{provider}' with model '{model}': {error}",
                    field="provider",
                ) from error
            if len(vector) != dimensions:
                raise ValidationError(
                    error_codes.EMBEDDING_DIMENSION_MISMATCH,
                    f"Model '{model}' produced a {len(vector)}-dimension vector, not the declared "
                    f"{dimensions}.",
                    field="dimensions",
                )
            self._chunks.resize_embedding_column(dimensions)

        settings = self._repository.upsert(
            provider, model, api_key, dimensions, chunk_size, chunk_overlap, base_url
        )
        return EmbeddingSettingsStatus(
            provider=settings.provider,
            model=settings.model,
            configured=True,
            base_url=settings.base_url,
            dimensions=settings.dimensions,
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
            dimensions=None,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
            updated_at=None,
        )
