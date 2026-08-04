from flask import Blueprint, jsonify, request

from app.application.web_crawl_settings_service import WebCrawlSettingsService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.web_crawl_settings_repository import WebCrawlSettingsRepository
from app.presentation.schemas import WebCrawlSettingsResponse, WebCrawlSettingsUpdateRequest

web_crawl_settings_bp = Blueprint("web_crawl_settings", __name__)


def _service() -> WebCrawlSettingsService:
    return WebCrawlSettingsService(WebCrawlSettingsRepository(get_session()))


@web_crawl_settings_bp.get("/web-crawl-settings")
@require_scope("web_crawl_settings:read")
def get_web_crawl_settings():
    settings = _service().get_status()
    return jsonify(WebCrawlSettingsResponse.from_entity(settings).model_dump(mode="json"))


@web_crawl_settings_bp.put("/web-crawl-settings")
@require_scope("web_crawl_settings:write")
def update_web_crawl_settings():
    dto = WebCrawlSettingsUpdateRequest.model_validate(request.get_json(silent=True) or {})
    settings = _service().update(dto.user_agent.strip())
    return jsonify(WebCrawlSettingsResponse.from_entity(settings).model_dump(mode="json"))
