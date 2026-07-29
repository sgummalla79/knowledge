from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from uuid import uuid4

from app.application.embedding_provider_settings_service import EmbeddingProviderSettingsService
from app.domain import error_codes
from app.domain.entities import EmbeddingProviderToggle
from app.domain.errors import ValidationError


def _toggle(provider, enabled=True):
    return EmbeddingProviderToggle(
        id=uuid4(), provider=provider, enabled=enabled, updated_at=datetime.now(timezone.utc)
    )


def test_list_providers_delegates_to_repository():
    repository = MagicMock()
    repository.list.return_value = [_toggle("ollama"), _toggle("voyage", enabled=False)]
    service = EmbeddingProviderSettingsService(repository)

    result = service.list_providers()

    assert result == repository.list.return_value


def test_set_enabled_persists_for_known_provider():
    repository = MagicMock()
    repository.set_enabled.return_value = _toggle("voyage", enabled=False)
    service = EmbeddingProviderSettingsService(repository)

    result = service.set_enabled("voyage", False)

    repository.set_enabled.assert_called_once_with("voyage", False)
    assert result.enabled is False


def test_set_enabled_rejects_unknown_provider():
    repository = MagicMock()
    service = EmbeddingProviderSettingsService(repository)

    with pytest.raises(ValidationError) as exc_info:
        service.set_enabled("made-up-provider", False)

    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER
    repository.set_enabled.assert_not_called()
