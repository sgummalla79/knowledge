from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.embedding_settings_service import EmbeddingSettingsService
from app.domain import error_codes
from app.domain.entities import EmbeddingSettings
from app.domain.errors import ValidationError


def _settings(**overrides):
    defaults = dict(
        id=uuid4(),
        provider="ollama",
        model="nomic-embed-text",
        api_key=None,
        base_url="http://ollama:11434",
        dimensions=768,
        chunk_size=800,
        chunk_overlap=100,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EmbeddingSettings(**defaults)


def _provider_settings_repo(enabled_providers=None):
    repo = MagicMock()
    repo.get_enabled_providers.return_value = enabled_providers or {"voyage", "ollama", "openai_compatible"}
    return repo


def _service(repository=None, chunk_repo=None, provider_settings_repo=None):
    return EmbeddingSettingsService(
        repository or MagicMock(), chunk_repo or MagicMock(), provider_settings_repo or _provider_settings_repo()
    )


def _mock_provider(vector):
    provider = MagicMock()
    provider.embed_query.return_value = vector
    return provider


def test_first_time_setup_verifies_and_resizes_before_persisting():
    repository = MagicMock()
    repository.get.return_value = None
    repository.upsert.return_value = _settings()
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    service = _service(repository, chunk_repo)

    with patch(
        "app.application.embedding_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 768),
    ):
        status = service.update("ollama", "nomic-embed-text", None, 768, 800, 100, "http://ollama:11434")

    chunk_repo.resize_embedding_column.assert_called_once_with(768)
    repository.upsert.assert_called_once()
    assert status.configured is True


def test_model_switch_locked_when_chunks_exist():
    repository = MagicMock()
    repository.get.return_value = _settings(provider="ollama", model="nomic-embed-text", dimensions=768)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    service = _service(repository, chunk_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.update("voyage", "voyage-3", "key", 1024, 800, 100, None)

    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LOCKED
    repository.upsert.assert_not_called()
    chunk_repo.resize_embedding_column.assert_not_called()


def test_model_switch_allowed_when_no_chunks_exist():
    repository = MagicMock()
    repository.get.return_value = _settings(provider="ollama", model="nomic-embed-text", dimensions=768)
    repository.upsert.return_value = _settings(provider="voyage", model="voyage-3", dimensions=1024, api_key="key")
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    service = _service(repository, chunk_repo)

    with patch(
        "app.application.embedding_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 1024),
    ):
        status = service.update("voyage", "voyage-3", "key", 1024, 800, 100, None)

    chunk_repo.resize_embedding_column.assert_called_once_with(1024)
    assert status.provider == "voyage"


def test_api_key_only_change_allowed_even_with_existing_chunks_and_skips_reverify():
    repository = MagicMock()
    repository.get.return_value = _settings(api_key="old-key")
    repository.upsert.return_value = _settings(api_key="new-key")
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    service = _service(repository, chunk_repo)

    with patch(
        "app.application.embedding_settings_service.EmbeddingProviderRegistry.resolve"
    ) as mock_resolve:
        service.update("ollama", "nomic-embed-text", "new-key", 768, 800, 100, "http://ollama:11434")
        mock_resolve.assert_not_called()

    chunk_repo.resize_embedding_column.assert_not_called()
    repository.upsert.assert_called_once()


def test_chunk_size_only_change_does_not_reverify_or_resize():
    repository = MagicMock()
    repository.get.return_value = _settings(chunk_size=800, chunk_overlap=100)
    repository.upsert.return_value = _settings(chunk_size=500, chunk_overlap=50)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    service = _service(repository, chunk_repo)

    with patch(
        "app.application.embedding_settings_service.EmbeddingProviderRegistry.resolve"
    ) as mock_resolve:
        service.update("ollama", "nomic-embed-text", None, 768, 500, 50, "http://ollama:11434")
        mock_resolve.assert_not_called()

    chunk_repo.resize_embedding_column.assert_not_called()


def test_live_verification_failure_raises_validation_error():
    repository = MagicMock()
    repository.get.return_value = None
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    service = _service(repository, chunk_repo)

    provider = MagicMock()
    provider.embed_query.side_effect = RuntimeError("connection refused")
    with patch(
        "app.application.embedding_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=provider,
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.update("ollama", "nomic-embed-text", None, 768, 800, 100, "http://ollama:11434")

    assert exc_info.value.code == error_codes.VALIDATION_ERROR
    repository.upsert.assert_not_called()
    chunk_repo.resize_embedding_column.assert_not_called()


def test_declared_dimensions_mismatching_actual_vector_length_raises():
    repository = MagicMock()
    repository.get.return_value = None
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    service = _service(repository, chunk_repo)

    with patch(
        "app.application.embedding_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 512),
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.update("ollama", "nomic-embed-text", None, 768, 800, 100, "http://ollama:11434")

    assert exc_info.value.code == error_codes.EMBEDDING_DIMENSION_MISMATCH
    repository.upsert.assert_not_called()
    chunk_repo.resize_embedding_column.assert_not_called()


def test_chunk_overlap_must_be_smaller_than_chunk_size():
    service = _service()
    with pytest.raises(ValidationError) as exc_info:
        service.update("ollama", "nomic-embed-text", None, 768, 100, 100, "http://ollama:11434")
    assert exc_info.value.field == "chunk_overlap"


def test_disabled_provider_rejected_before_touching_chunk_repo():
    repository = MagicMock()
    repository.get.return_value = None
    chunk_repo = MagicMock()
    provider_settings_repo = _provider_settings_repo(enabled_providers={"voyage"})
    service = _service(repository, chunk_repo, provider_settings_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.update("ollama", "nomic-embed-text", None, 768, 800, 100, "http://ollama:11434")

    assert exc_info.value.code == error_codes.EMBEDDING_PROVIDER_DISABLED
    chunk_repo.count_all.assert_not_called()
    repository.upsert.assert_not_called()
