from app.infrastructure.embeddings.bootstrap import bootstrap_embedding_provider_settings
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)


def test_bootstrap_seeds_every_known_provider_disabled(db_session):
    bootstrap_embedding_provider_settings(db_session)

    configs = {config.provider: config.enabled for config in EmbeddingProviderSettingsRepository(db_session).list()}

    assert configs.keys() == EmbeddingProviderRegistry.known_providers()
    assert all(enabled is False for enabled in configs.values())


def test_bootstrap_is_idempotent_and_does_not_touch_existing_rows(db_session):
    repo = EmbeddingProviderSettingsRepository(db_session)
    bootstrap_embedding_provider_settings(db_session)

    # An admin configures and enables ollama; a second bootstrap run must not stomp on that choice.
    repo.upsert_config("ollama", "nomic-embed-text", None, "http://ollama:11434", 768, 800, 100)
    repo.set_enabled("ollama", True)
    db_session.commit()

    bootstrap_embedding_provider_settings(db_session)

    configs = {config.provider: config.enabled for config in repo.list()}
    assert configs["ollama"] is True
