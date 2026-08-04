from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from app.domain.entities import WebCrawlSettings

# HTTP-layer wiring only — WebCrawlSettingsService is mocked. Real upsert behavior is covered by
# tests/integration/test_document_service.py (WebCrawlService's User-Agent usage).


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _settings(**overrides):
    fields = dict(user_agent="python-requests/2.32.3", updated_at=datetime.now(timezone.utc))
    fields.update(overrides)
    return WebCrawlSettings(**fields)


def test_get_status_returns_default_user_agent(client, auth_headers):
    with patch(
        "app.presentation.routes.web_crawl_settings.WebCrawlSettingsService.get_status",
        return_value=_settings(updated_at=None),
    ):
        response = client.get("/web-crawl-settings", headers=auth_headers("web_crawl_settings:read"))

    assert response.status_code == 200
    assert response.get_json()["user_agent"] == "python-requests/2.32.3"


def test_update_success_returns_updated_value(client, auth_headers):
    with patch(
        "app.presentation.routes.web_crawl_settings.WebCrawlSettingsService.update",
        return_value=_settings(user_agent="custom-agent/1.0"),
    ) as update:
        response = client.put(
            "/web-crawl-settings",
            json={"user_agent": "custom-agent/1.0"},
            headers=auth_headers("web_crawl_settings:write"),
        )

    assert response.status_code == 200
    assert response.get_json()["user_agent"] == "custom-agent/1.0"
    update.assert_called_once_with("custom-agent/1.0")


def test_update_empty_user_agent_returns_structured_400(client, auth_headers):
    response = client.put(
        "/web-crawl-settings",
        json={"user_agent": ""},
        headers=auth_headers("web_crawl_settings:write"),
    )

    assert response.status_code == 400


def test_missing_auth_returns_401(client):
    response = client.get("/web-crawl-settings")
    assert response.status_code == 401
