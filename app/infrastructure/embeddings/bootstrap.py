from sqlalchemy.exc import IntegrityError

from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)


def bootstrap_embedding_provider_settings(session) -> None:
    """Idempotent: seeds a row for any registered provider that doesn't already have one, so
    every provider adapter gets a row on the next app start without a fresh migration. Every
    provider starts unconfigured and disabled — an admin must configure and explicitly enable one
    via its dashboard page before any embedding/query calls work."""
    repository = EmbeddingProviderSettingsRepository(session)
    existing_providers = {config.provider for config in repository.list()}
    missing_providers = EmbeddingProviderRegistry.known_providers() - existing_providers
    if not missing_providers:
        return
    try:
        for provider in missing_providers:
            repository.set_enabled(provider, False)
        session.commit()
    except IntegrityError:
        session.rollback()
