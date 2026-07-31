from unittest.mock import MagicMock

from app.application.web_crawl_settings_service import WebCrawlSettingsService, default_web_crawl_settings
from app.constants import DEFAULT_WEB_CRAWL_USER_AGENT
from app.domain.entities import WebCrawlSettings


def test_get_status_falls_back_to_default_when_no_row_exists():
    repository = MagicMock()
    repository.get.return_value = None
    service = WebCrawlSettingsService(repository)

    status = service.get_status()

    assert status.user_agent == DEFAULT_WEB_CRAWL_USER_AGENT


def test_get_status_returns_stored_row_when_present():
    repository = MagicMock()
    repository.get.return_value = WebCrawlSettings(user_agent="custom-agent/1.0", updated_at=None)
    service = WebCrawlSettingsService(repository)

    status = service.get_status()

    assert status.user_agent == "custom-agent/1.0"


def test_update_delegates_to_repository_upsert():
    repository = MagicMock()
    repository.upsert.return_value = WebCrawlSettings(user_agent="python-requests/2.32.3", updated_at=None)
    service = WebCrawlSettingsService(repository)

    result = service.update("python-requests/2.32.3")

    repository.upsert.assert_called_once_with(user_agent="python-requests/2.32.3")
    assert result.user_agent == "python-requests/2.32.3"


def test_default_web_crawl_settings_has_no_updated_at():
    assert default_web_crawl_settings().updated_at is None
