from app.domain.entities import WebCrawlSettings as WebCrawlSettingsEntity
from app.infrastructure.orm import WebCrawlSettings as WebCrawlSettingsModel


def _to_entity(model: WebCrawlSettingsModel) -> WebCrawlSettingsEntity:
    return WebCrawlSettingsEntity(user_agent=model.user_agent, updated_at=model.updated_at)


class WebCrawlSettingsRepository:
    """Single global row — same application-level singleton pattern as SearchSettingsRepository.
    An absent row is not an error: WebCrawlSettingsService fills in DEFAULT_WEB_CRAWL_USER_AGENT
    when get() returns None."""

    def __init__(self, session):
        self._session = session

    def get(self) -> WebCrawlSettingsEntity | None:
        model = self._session.query(WebCrawlSettingsModel).first()
        return _to_entity(model) if model is not None else None

    def upsert(self, user_agent: str) -> WebCrawlSettingsEntity:
        existing = self._session.query(WebCrawlSettingsModel).first()
        if existing is None:
            existing = WebCrawlSettingsModel(user_agent=user_agent)
            self._session.add(existing)
        else:
            existing.user_agent = user_agent
        self._session.flush()
        return _to_entity(existing)
