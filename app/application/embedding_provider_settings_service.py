import logging
from dataclasses import dataclass
from datetime import datetime

from app.application.embedding_choice_validation import validate_provider_connection
from app.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.domain import error_codes
from app.domain.entities import EmbeddingProviderConfig
from app.domain.errors import ValidationError
from app.domain.ports import CategoryRepositoryPort, ChunkRepositoryPort, EmbeddingProviderSettingsRepositoryPort
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingProviderConfigStatus:
    provider: str
    enabled: bool
    configured: bool
    # True once this provider has chunks embedded with it — it can't be disabled (or have its
    # model identity changed) until every chunk is deleted, since embeddings from different
    # models aren't comparable.
    locked: bool
    # True when a *different* provider is the active one — since exactly one provider is ever
    # enabled at a time, this provider's config can't be touched at all (not even its api_key)
    # until that other provider is disabled first.
    locked_by_other: bool
    chunk_count: int
    model: str | None
    base_url: str | None
    dimensions: int | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None
    # The provider currently enabled system-wide, if any — surfaced on every status (including
    # this provider's own) so a caller never needs a second lookup to know who's active.
    active_provider: str | None


class EmbeddingProviderConfigService:
    """Owns the three known providers' embedding configuration and which one (if any) is the
    active one actually used for embedding. Exactly one provider may be enabled at a time — the
    app embeds with a single model per org, not a per-category choice — so enabling a provider
    disables whichever other one was active, and disabling/switching away from a provider that
    still has chunks is rejected until those chunks are deleted. Only the active provider's config
    can be edited; every other provider's config is fully locked until the active one is disabled,
    so there's never a "half-configured, not currently active" provider sitting around confusing
    which config will actually be used next."""

    def __init__(
        self,
        repository: EmbeddingProviderSettingsRepositoryPort,
        chunk_repo: ChunkRepositoryPort,
        category_repo: CategoryRepositoryPort,
    ):
        self._repository = repository
        self._chunks = chunk_repo
        self._categories = category_repo

    def list_status(self, org_id) -> list[EmbeddingProviderConfigStatus]:
        configs = {config.provider: config for config in self._repository.list(org_id)}
        chunk_count = self._chunks.count_all()
        active_provider = self._active_provider(configs.values())
        return [
            self._status(configs.get(provider), provider, chunk_count, active_provider)
            for provider in sorted(EmbeddingProviderRegistry.known_providers())
        ]

    def get_status(self, org_id, provider: str) -> EmbeddingProviderConfigStatus:
        self._require_known_provider(provider)
        configs = self._repository.list(org_id)
        active_provider = self._active_provider(configs)
        config = next((c for c in configs if c.provider == provider), None)
        return self._status(config, provider, self._chunks.count_all(), active_provider)

    def update_config(
        self,
        org_id,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> EmbeddingProviderConfigStatus:
        validate_provider_connection(provider, api_key, base_url)

        configs = self._repository.list(org_id)
        active_provider = self._active_provider(configs)
        if active_provider is not None and active_provider != provider:
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LOCKED,
                f"Provider '{active_provider}' is currently active — disable it before "
                f"configuring '{provider}'.",
                field="provider",
            )

        # Checked here, at save time, rather than only surfacing later as a failed ingestion job
        # when the first document is uploaded.
        if chunk_overlap >= chunk_size:
            raise ValidationError(
                error_codes.VALIDATION_ERROR,
                "chunk_overlap must be smaller than chunk_size.",
                field="chunk_overlap",
            )

        existing = next((c for c in configs if c.provider == provider), None)
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
            org_id, provider, model, api_key, base_url, dimensions, chunk_size, chunk_overlap
        )
        # The active provider's identity just changed — every cached category description_embedding
        # was computed with the *old* model and is now stale/wrong-dimension. Reuses the
        # provider_instance already resolved above for the connection test, no second HTTP call.
        if existing is not None and existing.enabled and identity_changed:
            self._resync_category_description_embeddings(org_id, provider_instance)
        return self._status(config, provider, chunk_count, active_provider)

    def enable(self, org_id, provider: str) -> EmbeddingProviderConfigStatus:
        config = self._repository.get(org_id, provider)
        if config is None or not config.model or not config.dimensions:
            raise ValidationError(
                error_codes.EMBEDDINGS_NOT_CONFIGURED,
                f"Configure provider '{provider}' before enabling it.",
                field="provider",
            )
        if config.enabled:
            return self._status(config, provider, self._chunks.count_all(), provider)

        currently_enabled = next((c for c in self._repository.list(org_id) if c.enabled), None)
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
            self._repository.set_enabled(org_id, currently_enabled.provider, False)

        # Guaranteed zero chunks whenever the active provider actually changes (the lock above),
        # so resizing the shared vector column here is always safe.
        self._chunks.resize_embedding_column(config.dimensions)
        # Unlike chunks, categories aren't locked behind chunk_count == 0 — a category can have a
        # description (and cached description_embedding) with zero documents. Every cached
        # embedding was computed against whichever provider was active before, so it's now
        # stale/wrong-dimension for this new one.
        provider_instance = EmbeddingProviderRegistry.resolve(provider, config.model, config.api_key, config.base_url)
        self._resync_category_description_embeddings(org_id, provider_instance)
        updated = self._repository.set_enabled(org_id, provider, True)
        return self._status(updated, provider, chunk_count, provider)

    def disable(self, org_id, provider: str) -> EmbeddingProviderConfigStatus:
        self._require_known_provider(provider)
        config = self._repository.get(org_id, provider)
        if config is None or not config.enabled:
            active_provider = self._active_provider(self._repository.list(org_id))
            return self._status(config, provider, self._chunks.count_all(), active_provider)

        chunk_count = self._chunks.count_all()
        if chunk_count > 0:
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LOCKED,
                f"Cannot disable provider '{provider}' while documents exist — delete all "
                "documents first.",
                field="provider",
            )
        updated = self._repository.set_enabled(org_id, provider, False)
        return self._status(updated, provider, chunk_count, None)

    def _resync_category_description_embeddings(self, org_id, provider_instance) -> None:
        """Called whenever the active embedding provider or its identity (model/base_url/
        dimensions) changes — the only two ways a category's description_embedding can go stale or
        wrong-dimension, mirroring the invariant this class already enforces for chunks.embedding
        (never leave vector data around from a different model). Unlike chunks, there's no
        "delete everything and retry" escape hatch for descriptions — they're meant to survive a
        provider switch — so this nulls every description_embedding first (synchronous, always
        safe, zero window where a stale-dimension vector could be queried) and then makes one
        best-effort batched attempt to recompute them all with the new provider. A failure here
        (rate limit, transient network error) is logged and left null rather than blocking the
        provider switch itself — those categories are simply excluded from router queries (same
        non-error fallback as a category with no description at all) until saved again or a retry
        succeeds.
        """
        categories = self._categories.list_all_with_description(org_id)
        self._categories.clear_all_description_embeddings(org_id)
        if not categories:
            return
        try:
            vectors = provider_instance.embed_documents([category.description for category in categories])
        except Exception:
            logger.warning(
                "Failed to re-embed category descriptions after embedding provider change; "
                "affected categories are excluded from router queries until saved again.",
                exc_info=True,
            )
            return
        for category, vector in zip(categories, vectors):
            self._categories.set_description_embedding(category.id, vector)

    def _active_provider(self, configs) -> str | None:
        active = next((c for c in configs if c.enabled), None)
        return active.provider if active is not None else None

    def _require_known_provider(self, provider: str) -> None:
        if provider not in EmbeddingProviderRegistry.known_providers():
            raise ValidationError(
                error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
                f"Unsupported embedding provider '{provider}'.",
                field="provider",
            )

    def _status(
        self,
        config: EmbeddingProviderConfig | None,
        provider: str,
        chunk_count: int,
        active_provider: str | None,
    ) -> EmbeddingProviderConfigStatus:
        locked_by_other = active_provider is not None and active_provider != provider
        if config is None:
            return EmbeddingProviderConfigStatus(
                provider=provider,
                enabled=False,
                configured=False,
                locked=False,
                locked_by_other=locked_by_other,
                chunk_count=0,
                model=None,
                base_url=None,
                dimensions=None,
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                updated_at=None,
                active_provider=active_provider,
            )
        return EmbeddingProviderConfigStatus(
            provider=config.provider,
            enabled=config.enabled,
            configured=config.model is not None,
            locked=config.enabled and chunk_count > 0,
            locked_by_other=locked_by_other,
            chunk_count=chunk_count if config.enabled else 0,
            model=config.model,
            base_url=config.base_url,
            dimensions=config.dimensions,
            chunk_size=config.chunk_size or DEFAULT_CHUNK_SIZE,
            chunk_overlap=config.chunk_overlap or DEFAULT_CHUNK_OVERLAP,
            updated_at=config.updated_at,
            active_provider=active_provider,
        )
