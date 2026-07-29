from sqlalchemy.exc import IntegrityError

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_OLLAMA_BASE_URL,
    EMBEDDING_DIM,
)
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository


def bootstrap_default_embedding_settings(session) -> None:
    """Idempotent: only seeds a row if none exists yet, so the app works fully locally out of the
    box (Ollama needs no api_key) without requiring a PUT /embedding-settings call first. The
    chunks.embedding column is already sized to EMBEDDING_DIM at table-creation time (migration
    0001), matching this default model, so no resize is needed here."""
    repository = EmbeddingSettingsRepository(session)
    if repository.get() is not None:
        return
    try:
        repository.upsert(
            DEFAULT_EMBEDDING_PROVIDER,
            DEFAULT_EMBEDDING_MODEL,
            None,
            EMBEDDING_DIM,
            DEFAULT_CHUNK_SIZE,
            DEFAULT_CHUNK_OVERLAP,
            DEFAULT_OLLAMA_BASE_URL,
        )
        session.commit()
    except IntegrityError:
        session.rollback()


def bootstrap_embedding_provider_settings(session) -> None:
    """Idempotent: seeds an enabled=True row for any registered provider that doesn't already
    have one, so every provider starts reachable out of the box and a newly-added provider
    adapter automatically gets a row on the next app start without a fresh migration."""
    repository = EmbeddingProviderSettingsRepository(session)
    existing_providers = {toggle.provider for toggle in repository.list()}
    missing_providers = EmbeddingProviderRegistry.known_providers() - existing_providers
    if not missing_providers:
        return
    try:
        for provider in missing_providers:
            repository.set_enabled(provider, True)
        session.commit()
    except IntegrityError:
        session.rollback()
