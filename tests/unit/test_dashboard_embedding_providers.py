from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import EmbeddingProviderConfig, WebCrawlSettings

# HTTP-layer only — WebCrawlSettingsService is mocked. Per-provider embedding configuration is now
# a React page (webui/src/pages/SettingsPage.tsx, webui/src/components/ProviderSettingsModal.tsx)
# calling the REST API directly — see tests/unit/test_embedding_settings_routes.py for that. This
# file only covers what's still server-rendered: the Web Crawler config page and the sidebar's
# provider status strip.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def _crawl_settings(user_agent="python-requests/2.32.3"):
    return WebCrawlSettings(user_agent=user_agent, updated_at=datetime.now(timezone.utc))


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.get_status", return_value=_crawl_settings())
def test_configuration_renders_web_crawl_user_agent(_get_status, _get_user, client):
    _logged_in(client)
    response = client.get("/dashboard/configuration")

    assert response.status_code == 200
    assert b"python-requests/2.32.3" in response.data


def test_configuration_requires_login(client):
    response = client.get("/dashboard/configuration")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


@patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=None)
@patch("app.presentation.routes.auth_ui.WebCrawlSettingsService.get_status", return_value=_crawl_settings())
def test_sidebar_shows_all_providers_with_active_one_highlighted(_get_status, _get_user, client):
    _logged_in(client)
    enabled_config = EmbeddingProviderConfig(
        id=uuid4(),
        provider="ollama",
        enabled=True,
        model="nomic-embed-text",
        api_key=None,
        base_url="http://ollama:11434",
        dimensions=768,
        chunk_size=800,
        chunk_overlap=100,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.presentation.routes.auth_ui.EmbeddingProviderSettingsRepository.list",
        return_value=[enabled_config],
    ):
        response = client.get("/dashboard/configuration")

    assert response.status_code == 200
    html = response.data.decode()
    strip_start = html.index('class="provider-status-strip"')
    strip = html[strip_start : strip_start + 600]
    # All three providers appear in the strip regardless of configuration state...
    assert "Voyage" in strip and "Ollama" in strip and "OpenAI" in strip
    # ...but only the active one is visually highlighted.
    assert "badge active" in strip
