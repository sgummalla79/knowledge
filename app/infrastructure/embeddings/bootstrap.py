from sqlalchemy.exc import IntegrityError

from app.constants import DEFAULT_DISABLED_EMBEDDING_PROVIDERS
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)


def bootstrap_embedding_provider_settings(session) -> None:
    """Idempotent: seeds a row for any registered provider that doesn't already have one, so
    every provider adapter gets a row on the next app start without a fresh migration.
    Providers in DEFAULT_DISABLED_EMBEDDING_PROVIDERS (e.g. "ollama", which has no bundled
    runtime to talk to now that it's out of docker-compose) start disabled; every other provider
    starts enabled and reachable out of the box."""
    repository = EmbeddingProviderSettingsRepository(session)
    existing_providers = {toggle.provider for toggle in repository.list()}
    missing_providers = EmbeddingProviderRegistry.known_providers() - existing_providers
    if not missing_providers:
        return
    try:
        for provider in missing_providers:
            repository.set_enabled(provider, provider not in DEFAULT_DISABLED_EMBEDDING_PROVIDERS)
        session.commit()
    except IntegrityError:
        session.rollback()
