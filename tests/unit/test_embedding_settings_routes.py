from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from app.application.embedding_settings_service import EmbeddingSettingsStatus
from app.domain.errors import ValidationError

# HTTP-layer wiring only — EmbeddingSettingsService is mocked. Real upsert/validation behavior
# is covered by tests/integration/test_ingestion_service.py and test_retrieval_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_get_status_not_configured(client, auth_headers):
    status = EmbeddingSettingsStatus(
        provider=None,
        model=None,
        configured=False,
        base_url=None,
        chunk_size=800,
        chunk_overlap=100,
        updated_at=None,
    )
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.get_status",
        return_value=status,
    ):
        response = client.get("/embedding-settings", headers=auth_headers("embedding_settings:read"))

    assert response.status_code == 200
    body = response.get_json()
    assert body["configured"] is False
    assert body["provider"] is None
    assert body["chunk_size"] == 800


def test_get_status_configured(client, auth_headers):
    status = EmbeddingSettingsStatus(
        provider="ollama",
        model="nomic-embed-text",
        configured=True,
        base_url="http://ollama:11434",
        chunk_size=800,
        chunk_overlap=100,
        updated_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.get_status",
        return_value=status,
    ):
        response = client.get("/embedding-settings", headers=auth_headers("embedding_settings:read"))

    body = response.get_json()
    assert body["configured"] is True
    assert body["provider"] == "ollama"
    assert body["model"] == "nomic-embed-text"
    assert body["base_url"] == "http://ollama:11434"
    assert "api_key" not in body


def test_update_unsupported_voyage_model_returns_structured_400(client, auth_headers):
    # voyage-3 produces 1024-dim vectors, incompatible with this deployment's EMBEDDING_DIM (768),
    # and "voyage" isn't a key in SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER at all anymore — real
    # (unmocked) validate_embedding_choice rejects it as an unsupported provider before any DB
    # access happens.
    response = client.put(
        "/embedding-settings",
        json={"provider": "voyage", "model": "voyage-3", "api_key": "secret"},
        headers=auth_headers("embedding_settings:write"),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "embedding_provider"


def test_update_ollama_without_api_key_accepted_by_schema(client, auth_headers):
    # Ollama is self-hosted/keyless — proves api_key is genuinely optional end-to-end at the HTTP
    # layer, not just required-with-empty-string.
    status = EmbeddingSettingsStatus(
        provider="ollama",
        model="nomic-embed-text",
        configured=True,
        base_url="http://ollama:11434",
        chunk_size=800,
        chunk_overlap=100,
        updated_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.update",
        return_value=status,
    ):
        response = client.put(
            "/embedding-settings",
            json={"provider": "ollama", "model": "nomic-embed-text"},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["configured"] is True
    assert body["base_url"] == "http://ollama:11434"


def test_update_unsupported_model_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.update",
        side_effect=ValidationError("unsupported_embedding_provider", "bad model", field="embedding_model"),
    ):
        response = client.put(
            "/embedding-settings",
            json={"provider": "voyage", "model": "bogus", "api_key": "secret"},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "unsupported_embedding_provider"


def test_update_bad_chunking_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.update",
        side_effect=ValidationError("validation_error", "bad chunking", field="chunk_overlap"),
    ):
        response = client.put(
            "/embedding-settings",
            json={"provider": "voyage", "model": "voyage-3", "api_key": "secret", "chunk_size": 10, "chunk_overlap": 20},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "chunk_overlap"


def test_update_success_returns_configured_true(client, auth_headers):
    status = EmbeddingSettingsStatus(
        provider="ollama",
        model="nomic-embed-text",
        configured=True,
        base_url="http://ollama:11434",
        chunk_size=800,
        chunk_overlap=100,
        updated_at=datetime.now(timezone.utc),
    )
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.update",
        return_value=status,
    ):
        response = client.put(
            "/embedding-settings",
            json={"provider": "ollama", "model": "nomic-embed-text"},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    assert response.get_json()["configured"] is True


def test_missing_auth_returns_401(client):
    response = client.get("/embedding-settings")
    assert response.status_code == 401


def test_delete_clears_settings_and_returns_configured_false(client, auth_headers):
    status = EmbeddingSettingsStatus(
        provider=None,
        model=None,
        configured=False,
        base_url=None,
        chunk_size=800,
        chunk_overlap=100,
        updated_at=None,
    )
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingSettingsService.clear",
        return_value=status,
    ):
        response = client.delete("/embedding-settings", headers=auth_headers("embedding_settings:write"))

    assert response.status_code == 200
    body = response.get_json()
    assert body["configured"] is False
    assert body["provider"] is None
