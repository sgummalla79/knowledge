from unittest.mock import MagicMock

from app.application.router_settings_service import RouterSettingsService, default_router_settings
from app.constants import DEFAULT_ROUTER_MIN_SIMILARITY, DEFAULT_ROUTER_TOP_N


def test_get_status_returns_defaults_when_no_row_exists():
    repository = MagicMock()
    repository.get.return_value = None
    service = RouterSettingsService(repository)

    settings = service.get_status()

    assert settings == default_router_settings()
    assert settings.top_n == DEFAULT_ROUTER_TOP_N
    assert settings.min_similarity == DEFAULT_ROUTER_MIN_SIMILARITY


def test_update_passes_values_through_to_the_repository():
    repository = MagicMock()
    service = RouterSettingsService(repository)

    service.update(top_n=5, min_similarity=0.7)

    repository.upsert.assert_called_once_with(top_n=5, min_similarity=0.7)
