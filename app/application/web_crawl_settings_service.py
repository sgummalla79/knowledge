from app.constants import DEFAULT_WEB_CRAWL_USER_AGENT
from app.domain.entities import WebCrawlSettings
from app.domain.ports import WebCrawlSettingsRepositoryPort


def default_web_crawl_settings() -> WebCrawlSettings:
    """Shared fallback when no row exists yet — mirrors default_search_settings()."""
    return WebCrawlSettings(user_agent=DEFAULT_WEB_CRAWL_USER_AGENT, updated_at=None)


class WebCrawlSettingsService:
    def __init__(self, repository: WebCrawlSettingsRepositoryPort):
        self._repository = repository

    def get_status(self) -> WebCrawlSettings:
        return self._repository.get() or default_web_crawl_settings()

    def update(self, user_agent: str) -> WebCrawlSettings:
        return self._repository.upsert(user_agent=user_agent)
