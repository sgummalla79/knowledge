from dataclasses import dataclass
from datetime import datetime

from app.application.embedding_choice_validation import validate_provider_connection
from app.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.domain import error_codes
from app.domain.entities import EmbeddingProviderConfig
from app.domain.errors import ValidationError
from app.domain.ports import ChunkRepositoryPort, EmbeddingProviderSettingsRepositoryPort
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


@dataclass(frozen=True)
class EmbeddingProviderConfigStatus:
    provider: str
    enabled: bool
    configured: bool
    # True once this provider has chunks embedded with it — it can't be disabled (or have its
    # model identity changed) until every chunk is deleted, since embeddings from different
    # models aren't comparable.
    locked: bool
    chunk_count: int
    model: str | None
    base_url: str | None
    dimensions: int | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None


class EmbeddingProviderConfigService:
    """Owns the three known providers' embedding configuration and which one (if any) is the
    active one actually used for embedding. Exactly one provider may be enabled at a time — the
    app embeds with a single global model, not a per-library choice — so enabling a provider
    disables whichever other one was active, and disabling/switching away from a provider that
    still has chunks is rejected until those chunks are deleted."""

    def __init__(self, repository: EmbeddingProviderSettingsRepositoryPort, chunk_repo: ChunkRepositoryPort):
        self._repository = repository
        self._chunks = chunk_repo

    def list_status(self) -> list[EmbeddingProviderConfigStatus]:
        configs = {config.provider: config for config in self._repository.list()}
        chunk_count = self._chunks.count_all()
        return [
            self._status(configs.get(provider), provider, chunk_count)
            for provider in sorted(EmbeddingProviderRegistry.known_providers())
        ]

    def get_status(self, provider: str) -> EmbeddingProviderConfigStatus:
        self._require_known_provider(provider)
        return self._status(self._repository.get(provider), provider, self._chunks.count_all())

    def update_config(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> EmbeddingProviderConfigStatus:
        validate_provider_connection(provider, api_key, base_url)
        # Checked here, at save time, rather than only surfacing later as a failed ingestion job
        # when the first document is uploaded.
        if chunk_overlap >= chunk_size:
            raise ValidationError(
                error_codes.VALIDATION_ERROR,
                "chunk_overlap must be smaller than chunk_size.",
                field="chunk_overlap",
            )

        existing = self._repository.get(provider)
        identity_changed = existing is not None and (
            existing.model != model or existing.base_url != base_url or existing.dimensions != dimensions
        )
        chunk_count = self._chunks.count_all()
        if existing is not None and existing.enabled and identity_changed and chunk_count > 0:
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LOCKED,
                "Cannot change the model/base_url/dimensions of the active embedding provider "
                "while documents exist — delete all documents first, since embeddings from "
                "different models are not comparable.",
                field="model",
            )

        # A brand-new configuration, or any change to model/base_url/dimensions: verify the
        # endpoint is reachable and actually produces vectors of the declared length before
        # persisting, so a bad credential or wrong dimensions surfaces here as a clear error
        # instead of a cryptic failure during ingestion.
        if existing is None or identity_changed:
            provider_instance = EmbeddingProviderRegistry.resolve(provider, model, api_key, base_url)
            try:
                vector = provider_instance.embed_query("connection test")
            except Exception as error:
                raise ValidationError(
                    error_codes.VALIDATION_ERROR,
                    f"Could not verify embedding provider '{provider}' with model '{model}': {error}",
                    field="model",
                ) from error
            if len(vector) != dimensions:
                raise ValidationError(
                    error_codes.EMBEDDING_DIMENSION_MISMATCH,
                    f"Model '{model}' produced a {len(vector)}-dimension vector, not the declared "
                    f"{dimensions}.",
                    field="dimensions",
                )

        config = self._repository.upsert_config(
            provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap
        )
        return self._status(config, provider, chunk_count)

    def enable(self, provider: str) -> EmbeddingProviderConfigStatus:
        config = self._repository.get(provider)
        if config is None or not config.model or not config.dimensions:
            raise ValidationError(
                error_codes.EMBEDDINGS_NOT_CONFIGURED,
                f"Configure provider '{provider}' before enabling it.",
                field="provider",
            )
        if config.enabled:
            return self._status(config, provider, self._chunks.count_all())

        currently_enabled = next((c for c in self._repository.list() if c.enabled), None)
        chunk_count = self._chunks.count_all()
        if currently_enabled is not None:
            if chunk_count > 0:
                raise ValidationError(
                    error_codes.EMBEDDING_MODEL_LOCKED,
                    f"Cannot switch the active embedding provider away from "
                    f"'{currently_enabled.provider}' while documents exist — delete all "
                    "documents first, since embeddings from different models are not comparable.",
                    field="provider",
                )
            self._repository.set_enabled(currently_enabled.provider, False)

        # Guaranteed zero chunks whenever the active provider actually changes (the lock above),
        # so resizing the shared vector column here is always safe.
        self._chunks.resize_embedding_column(config.dimensions)
        updated = self._repository.set_enabled(provider, True)
        return self._status(updated, provider, chunk_count)

    def disable(self, provider: str) -> EmbeddingProviderConfigStatus:
        self._require_known_provider(provider)
        config = self._repository.get(provider)
        if config is None or not config.enabled:
            return self._status(config, provider, self._chunks.count_all())

        chunk_count = self._chunks.count_all()
        if chunk_count > 0:
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LOCKED,
                f"Cannot disable provider '{provider}' while documents exist — delete all "
                "documents first.",
                field="provider",
            )
        updated = self._repository.set_enabled(provider, False)
        return self._status(updated, provider, chunk_count)

    def _require_known_provider(self, provider: str) -> None:
        if provider not in EmbeddingProviderRegistry.known_providers():
            raise ValidationError(
                error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
                f"Unsupported embedding provider '{provider}'.",
                field="provider",
            )

    def _status(
        self, config: EmbeddingProviderConfig | None, provider: str, chunk_count: int
    ) -> EmbeddingProviderConfigStatus:
        if config is None:
            return EmbeddingProviderConfigStatus(
                provider=provider,
                enabled=False,
                configured=False,
                locked=False,
                chunk_count=0,
                model=None,
                base_url=None,
                dimensions=None,
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                updated_at=None,
            )
        return EmbeddingProviderConfigStatus(
            provider=config.provider,
            enabled=config.enabled,
            configured=config.model is not None,
            locked=config.enabled and chunk_count > 0,
            chunk_count=chunk_count if config.enabled else 0,
            model=config.model,
            base_url=config.base_url,
            dimensions=config.dimensions,
            chunk_size=config.chunk_size or DEFAULT_CHUNK_SIZE,
            chunk_overlap=config.chunk_overlap or DEFAULT_CHUNK_OVERLAP,
            updated_at=config.updated_at,
        )
