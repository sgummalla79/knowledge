import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_embedding_options_flags_ollama_as_keyless_and_base_url_supported(client, auth_headers):
    response = client.get("/embedding-options", headers=auth_headers())

    assert response.status_code == 200
    body = response.get_json()
    assert body["default_provider"] == "ollama"
    assert body["default_model"] == "nomic-embed-text"
    assert body["dimensions"] == 768

    providers_by_name = {provider["name"]: provider for provider in body["providers"]}
    ollama = providers_by_name["ollama"]
    assert ollama["api_key_required"] is False
    assert ollama["base_url_supported"] is True
    assert ollama["default_base_url"] == "http://ollama:11434"
    assert "voyage" not in providers_by_name


def test_rerank_options_has_no_supported_providers(client, auth_headers):
    # Voyage was the only rerank provider and is now inactive (same reasoning as embeddings) —
    # an empty providers list is the signal to clients that reranking isn't offered right now.
    response = client.get("/rerank-options", headers=auth_headers())

    assert response.status_code == 200
    assert response.get_json()["providers"] == []
