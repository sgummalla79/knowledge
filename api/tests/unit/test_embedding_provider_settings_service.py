from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from api.domain import error_codes
from api.domain.entities import EmbeddingProviderConfig
from api.domain.errors import ValidationError

_ORG_ID = uuid4()


def _config(provider="openai_compatible", enabled=False, **overrides):
    defaults = dict(
        id=uuid4(),
        provider=provider,
        enabled=enabled,
        model="text-embedding-3-small",
        api_key=None,
        base_url="https://api.example.com/v1",
        dimensions=768,
        chunk_size=800,
        chunk_overlap=100,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EmbeddingProviderConfig(**defaults)


def _mock_provider(vector):
    provider = MagicMock()
    provider.embed_query.return_value = vector
    return provider


def test_list_status_covers_every_known_provider_even_when_unconfigured():
    repository = MagicMock()
    repository.list.return_value = [_config("openai_compatible", enabled=True)]
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    statuses = {status.provider: status for status in service.list_status(_ORG_ID)}

    assert set(statuses) == {"voyage", "openai_compatible"}
    assert statuses["openai_compatible"].configured is True
    assert statuses["openai_compatible"].enabled is True
    assert statuses["voyage"].configured is False
    assert statuses["voyage"].enabled is False


def test_list_status_marks_non_active_providers_as_locked_by_other():
    repository = MagicMock()
    repository.list.return_value = [_config("openai_compatible", enabled=True)]
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    statuses = {status.provider: status for status in service.list_status(_ORG_ID)}

    assert statuses["openai_compatible"].locked_by_other is False
    assert statuses["openai_compatible"].active_provider == "openai_compatible"
    assert statuses["voyage"].locked_by_other is True
    assert statuses["voyage"].active_provider == "openai_compatible"


def test_list_status_nothing_locked_when_no_provider_is_active():
    repository = MagicMock()
    repository.list.return_value = []
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    statuses = service.list_status(_ORG_ID)

    assert all(status.locked_by_other is False for status in statuses)
    assert all(status.active_provider is None for status in statuses)


def test_get_status_unknown_provider_raises():
    service = EmbeddingProviderConfigService(MagicMock(), MagicMock(), MagicMock())
    with pytest.raises(ValidationError) as exc_info:
        service.get_status(_ORG_ID, "made-up-provider")
    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER


def test_update_config_first_time_verifies_and_persists():
    repository = MagicMock()
    repository.list.return_value = []
    repository.upsert_config.return_value = _config()
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 768),
    ):
        status = service.update_config(_ORG_ID, "openai_compatible", "text-embedding-3-small", None, "https://api.example.com/v1", 768, 800, 100)

    repository.upsert_config.assert_called_once_with(
        _ORG_ID, "openai_compatible", "text-embedding-3-small", None, "https://api.example.com/v1", 768, 800, 100
    )
    assert status.configured is True


def test_update_config_blocked_when_a_different_provider_is_active():
    repository = MagicMock()
    repository.list.return_value = [_config("openai_compatible", enabled=True)]
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.update_config(_ORG_ID, "voyage", "voyage-3", "key", None, 1024, 800, 100)

    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LOCKED
    assert exc_info.value.field == "provider"
    repository.upsert_config.assert_not_called()


def test_update_config_locked_when_provider_is_active_and_chunks_exist():
    repository = MagicMock()
    repository.list.return_value = [_config("openai_compatible", enabled=True, model="text-embedding-3-small", dimensions=768)]
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.update_config(_ORG_ID, "openai_compatible", "different-model", None, "https://api.example.com/v1", 768, 800, 100)

    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LOCKED
    repository.upsert_config.assert_not_called()


def test_update_config_identity_change_allowed_when_no_provider_is_active():
    # Nothing is active yet, so this provider's own (never-embedded-with) config can change freely
    # even though chunks happen to exist in the DB from a since-disabled provider.
    repository = MagicMock()
    repository.list.return_value = [_config("voyage", enabled=False, model="voyage-2", dimensions=1024, api_key="key")]
    repository.upsert_config.return_value = _config("voyage", model="voyage-3", dimensions=1024, api_key="key")
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 1024),
    ):
        status = service.update_config(_ORG_ID, "voyage", "voyage-3", "key", None, 1024, 800, 100)

    assert status.provider == "voyage"
    repository.upsert_config.assert_called_once()


def test_update_config_api_key_only_change_skips_reverify():
    repository = MagicMock()
    repository.list.return_value = [_config(api_key="old-key")]
    repository.upsert_config.return_value = _config(api_key="new-key")
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve"
    ) as mock_resolve:
        service.update_config(_ORG_ID, "openai_compatible", "text-embedding-3-small", "new-key", "https://api.example.com/v1", 768, 800, 100)
        mock_resolve.assert_not_called()

    repository.upsert_config.assert_called_once()


def test_update_config_chunk_size_only_change_does_not_reverify():
    repository = MagicMock()
    repository.list.return_value = [_config(chunk_size=800, chunk_overlap=100)]
    repository.upsert_config.return_value = _config(chunk_size=500, chunk_overlap=50)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve"
    ) as mock_resolve:
        service.update_config(_ORG_ID, "openai_compatible", "text-embedding-3-small", None, "https://api.example.com/v1", 768, 500, 50)
        mock_resolve.assert_not_called()


def test_update_config_live_verification_failure_raises():
    repository = MagicMock()
    repository.list.return_value = []
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    provider = MagicMock()
    provider.embed_query.side_effect = RuntimeError("connection refused")
    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=provider,
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.update_config(_ORG_ID, "openai_compatible", "text-embedding-3-small", None, "https://api.example.com/v1", 768, 800, 100)

    assert exc_info.value.code == error_codes.VALIDATION_ERROR
    repository.upsert_config.assert_not_called()


def test_update_config_declared_dimensions_mismatching_actual_vector_length_raises():
    repository = MagicMock()
    repository.list.return_value = []
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 512),
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.update_config(_ORG_ID, "openai_compatible", "text-embedding-3-small", None, "https://api.example.com/v1", 768, 800, 100)

    assert exc_info.value.code == error_codes.EMBEDDING_DIMENSION_MISMATCH
    repository.upsert_config.assert_not_called()


def test_update_config_chunk_overlap_must_be_smaller_than_chunk_size():
    repository = MagicMock()
    repository.list.return_value = []
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.update_config(_ORG_ID, "openai_compatible", "text-embedding-3-small", None, "https://api.example.com/v1", 768, 100, 100)
    assert exc_info.value.field == "chunk_overlap"


def test_enable_requires_configured_provider():
    repository = MagicMock()
    repository.get.return_value = None
    chunk_repo = MagicMock()
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.enable(_ORG_ID, "voyage")

    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED
    repository.set_enabled.assert_not_called()


def test_enable_already_enabled_is_a_noop():
    repository = MagicMock()
    repository.get.return_value = _config("openai_compatible", enabled=True)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 3
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    status = service.enable(_ORG_ID, "openai_compatible")

    assert status.enabled is True
    repository.set_enabled.assert_not_called()
    chunk_repo.resize_embedding_column.assert_not_called()


def test_enable_switches_active_provider_when_previous_has_no_chunks():
    repository = MagicMock()
    voyage_config = _config("voyage", enabled=False, model="voyage-3", dimensions=1024)
    openai_config = _config("openai_compatible", enabled=True)
    repository.get.return_value = voyage_config
    repository.list.return_value = [openai_config, voyage_config]
    repository.set_enabled.return_value = _config("voyage", enabled=True, dimensions=1024)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with patch(
        "api.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 1024),
    ):
        status = service.enable(_ORG_ID, "voyage")

    repository.set_enabled.assert_any_call(_ORG_ID, "openai_compatible", False)
    repository.set_enabled.assert_any_call(_ORG_ID, "voyage", True)
    chunk_repo.resize_embedding_column.assert_called_once_with(1024)
    category_repo.list_all_with_description.assert_called_once()
    category_repo.clear_all_description_embeddings.assert_called_once()
    assert status.enabled is True
    assert status.active_provider == "voyage"


def test_enable_blocked_when_other_active_provider_has_chunks():
    repository = MagicMock()
    voyage_config = _config("voyage", enabled=False, model="voyage-3", dimensions=1024)
    openai_config = _config("openai_compatible", enabled=True)
    repository.get.return_value = voyage_config
    repository.list.return_value = [openai_config, voyage_config]
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 5
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.enable(_ORG_ID, "voyage")

    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LOCKED
    repository.set_enabled.assert_not_called()
    chunk_repo.resize_embedding_column.assert_not_called()


def test_disable_not_enabled_is_a_noop():
    repository = MagicMock()
    repository.get.return_value = _config("openai_compatible", enabled=False)
    repository.list.return_value = [_config("openai_compatible", enabled=False)]
    chunk_repo = MagicMock()
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    service.disable(_ORG_ID, "openai_compatible")

    repository.set_enabled.assert_not_called()


def test_disable_blocked_when_chunks_exist():
    repository = MagicMock()
    repository.get.return_value = _config("openai_compatible", enabled=True)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 1
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.disable(_ORG_ID, "openai_compatible")

    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LOCKED
    repository.set_enabled.assert_not_called()


def test_disable_succeeds_when_no_chunks_exist():
    repository = MagicMock()
    repository.get.return_value = _config("openai_compatible", enabled=True)
    repository.set_enabled.return_value = _config("openai_compatible", enabled=False)
    chunk_repo = MagicMock()
    chunk_repo.count_all.return_value = 0
    category_repo = MagicMock()
    category_repo.list_all_with_description.return_value = []
    service = EmbeddingProviderConfigService(repository, chunk_repo, category_repo)

    status = service.disable(_ORG_ID, "openai_compatible")

    repository.set_enabled.assert_called_once_with(_ORG_ID, "openai_compatible", False)
    assert status.enabled is False
    assert status.active_provider is None
