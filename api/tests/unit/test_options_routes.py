from datetime import datetime, timezone
from unittest.mock import patch

from uuid import uuid4

import pytest

from api import create_app
from api.application.embedding_provider_settings_service import EmbeddingProviderConfigStatus


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    # Every resource route now requires a real session (require_org_session) rather than a
    # bootstrap default (see docs/DATA_MODEL.md) — seeded once here so route tests can focus on
    # the behavior they're actually testing.
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
    return test_client


def _status(provider, enabled=False, configured=False, model=None, locked=False):
    return EmbeddingProviderConfigStatus(
        provider=provider,
        enabled=enabled,
        configured=configured,
        locked=locked,
        locked_by_other=False,
        chunk_count=0,
        model=model,
        base_url=None,
        dimensions=768 if configured else None,
        chunk_size=800,
        chunk_overlap=100,
        updated_at=datetime.now(timezone.utc) if configured else None,
        active_provider=provider if enabled else None
    )


def test_embedding_options_describes_provider_capabilities(client):
    statuses = [_status("voyage"), _status("ollama", locked=True), _status("openai_compatible")]
    with patch(
        "api.presentation.routes.options.EmbeddingProviderConfigService.list_status",
        return_value=statuses
    ):
        response = client.get("/embedding-options")

    assert response.status_code == 200
    body = response.get_json()
    # No provider is enabled by default anymore — nothing sensible to point at.
    assert body["default_provider"] is None
    assert body["default_model"] is None
    assert isinstance(body["suggested_models"], list)

    providers_by_name = {provider["name"]: provider for provider in body["providers"]}
    ollama = providers_by_name["ollama"]
    assert ollama["display_name"] == "Ollama"
    assert ollama["locked"] is True
    assert ollama["api_key_required"] is False
    assert ollama["base_url_required"] is False
    assert ollama["base_url_supported"] is True
    assert ollama["default_base_url"] == "http://ollama:11434"

    # Any registered provider is now reachable — not just the one whitelisted (provider, model).
    voyage = providers_by_name["voyage"]
    assert voyage["api_key_required"] is True
    assert voyage["base_url_supported"] is False

    openai_compatible = providers_by_name["openai_compatible"]
    assert openai_compatible["base_url_required"] is True

    assert ollama["supports_model_listing"] is True
    assert openai_compatible["supports_model_listing"] is True
    assert voyage["supports_model_listing"] is False


def test_crawl_options_exposes_the_max_pages_limit(client):
    from api.constants import WEB_CRAWL_MAX_PAGES_LIMIT

    response = client.get("/crawl-options")

    assert response.status_code == 200
    assert response.get_json() == {"max_pages_limit": WEB_CRAWL_MAX_PAGES_LIMIT}


def test_embedding_options_lists_every_known_provider_regardless_of_state(client):
    # There's no more "selectable in a dropdown" toggle gating this list — every provider is
    # always listed, whether configured/enabled or not, since the dashboard renders a fixed page
    # per provider instead of picking from a filtered list.
    with patch(
        "api.presentation.routes.options.EmbeddingProviderConfigService.list_status",
        return_value=[_status("voyage"), _status("ollama", enabled=True, configured=True, model="nomic-embed-text"), _status("openai_compatible")]
    ):
        response = client.get("/embedding-options")

    body = response.get_json()
    provider_names = {provider["name"] for provider in body["providers"]}
    assert provider_names == {"voyage", "ollama", "openai_compatible"}
    assert body["default_provider"] == "ollama"
    assert body["default_model"] == "nomic-embed-text"
