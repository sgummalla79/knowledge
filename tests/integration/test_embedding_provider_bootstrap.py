from app.constants import DEFAULT_DISABLED_EMBEDDING_PROVIDERS
from app.infrastructure.embeddings.bootstrap import bootstrap_embedding_provider_settings
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)


def test_bootstrap_seeds_ollama_disabled_and_others_enabled(db_session):
    bootstrap_embedding_provider_settings(db_session)

    toggles = {toggle.provider: toggle.enabled for toggle in EmbeddingProviderSettingsRepository(db_session).list()}

    assert toggles.keys() == EmbeddingProviderRegistry.known_providers()
    for provider in DEFAULT_DISABLED_EMBEDDING_PROVIDERS:
        assert toggles[provider] is False
    for provider in EmbeddingProviderRegistry.known_providers() - DEFAULT_DISABLED_EMBEDDING_PROVIDERS:
        assert toggles[provider] is True


def test_bootstrap_is_idempotent_and_does_not_touch_existing_rows(db_session):
    repo = EmbeddingProviderSettingsRepository(db_session)
    bootstrap_embedding_provider_settings(db_session)

    # An admin re-enables ollama; a second bootstrap run must not stomp on that choice.
    repo.set_enabled("ollama", True)
    db_session.commit()

    bootstrap_embedding_provider_settings(db_session)

    toggles = {toggle.provider: toggle.enabled for toggle in repo.list()}
    assert toggles["ollama"] is True
