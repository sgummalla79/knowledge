from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from uuid import uuid4

from app import create_app
from app.domain.entities import EmbeddingProviderToggle


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _toggle(provider, enabled):
    return EmbeddingProviderToggle(
        id=uuid4(), provider=provider, enabled=enabled, updated_at=datetime.now(timezone.utc)
    )


def test_embedding_options_describes_provider_capabilities(client, auth_headers):
    all_enabled = [_toggle("voyage", True), _toggle("ollama", True), _toggle("openai_compatible", True)]
    with patch(
        "app.presentation.routes.options.EmbeddingProviderSettingsService.list_providers",
        return_value=all_enabled,
    ):
        response = client.get("/embedding-options", headers=auth_headers())

    assert response.status_code == 200
    body = response.get_json()
    # No provider is bundled/enabled by default anymore — nothing sensible to point at.
    assert body["default_provider"] is None
    assert body["default_model"] is None
    assert isinstance(body["suggested_models"], list)

    providers_by_name = {provider["name"]: provider for provider in body["providers"]}
    ollama = providers_by_name["ollama"]
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


def test_embedding_options_excludes_disabled_providers(client, auth_headers):
    with patch(
        "app.presentation.routes.options.EmbeddingProviderSettingsService.list_providers",
        return_value=[_toggle("voyage", False), _toggle("ollama", True), _toggle("openai_compatible", False)],
    ):
        response = client.get("/embedding-options", headers=auth_headers())

    body = response.get_json()
    provider_names = {provider["name"] for provider in body["providers"]}
    assert provider_names == {"ollama"}


def test_rerank_options_has_no_supported_providers(client, auth_headers):
    # Voyage was the only rerank provider and is now inactive (same reasoning as embeddings) —
    # an empty providers list is the signal to clients that reranking isn't offered right now.
    response = client.get("/rerank-options", headers=auth_headers())

    assert response.status_code == 200
    assert response.get_json()["providers"] == []
