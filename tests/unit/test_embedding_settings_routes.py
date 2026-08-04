from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from app.application.embedding_provider_settings_service import EmbeddingProviderConfigStatus
from app.domain.errors import ValidationError

# HTTP-layer wiring only — EmbeddingProviderConfigService is mocked. Real upsert/validation/
# locking behavior is covered by tests/unit/test_embedding_provider_settings_service.py and
# tests/integration/test_ingestion_service.py / test_retrieval_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _status(provider="ollama", enabled=False, configured=False, locked=False, chunk_count=0, **overrides):
    defaults = dict(
        provider=provider,
        enabled=enabled,
        configured=configured,
        locked=locked,
        locked_by_other=False,
        chunk_count=chunk_count,
        model="nomic-embed-text" if configured else None,
        base_url="http://ollama:11434" if configured else None,
        dimensions=768 if configured else None,
        chunk_size=800,
        chunk_overlap=100,
        updated_at=datetime.now(timezone.utc) if configured else None,
        active_provider=provider if enabled else None,
    )
    defaults.update(overrides)
    return EmbeddingProviderConfigStatus(**defaults)


def test_list_returns_all_providers(client, auth_headers):
    statuses = [_status("ollama", enabled=True, configured=True), _status("voyage"), _status("openai_compatible")]
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.list_status",
        return_value=statuses,
    ):
        response = client.get("/embedding-settings", headers=auth_headers("embedding_settings:read"))

    assert response.status_code == 200
    body = response.get_json()
    assert {item["provider"]: item["enabled"] for item in body} == {
        "ollama": True,
        "voyage": False,
        "openai_compatible": False,
    }


def test_get_status_not_configured(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.get_status",
        return_value=_status("voyage"),
    ):
        response = client.get("/embedding-settings/voyage", headers=auth_headers("embedding_settings:read"))

    assert response.status_code == 200
    body = response.get_json()
    assert body["configured"] is False
    assert body["enabled"] is False
    assert body["provider"] == "voyage"
    assert body["chunk_size"] == 800


def test_get_status_configured_and_enabled(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.get_status",
        return_value=_status("ollama", enabled=True, configured=True),
    ):
        response = client.get("/embedding-settings/ollama", headers=auth_headers("embedding_settings:read"))

    body = response.get_json()
    assert body["configured"] is True
    assert body["enabled"] is True
    assert body["model"] == "nomic-embed-text"
    assert body["base_url"] == "http://ollama:11434"
    assert body["dimensions"] == 768
    assert "api_key" not in body


def test_update_missing_dimensions_rejected_by_schema(client, auth_headers):
    # dimensions is a required field — no static map to infer it from.
    response = client.put(
        "/embedding-settings/ollama",
        json={"model": "nomic-embed-text"},
        headers=auth_headers("embedding_settings:write"),
    )

    assert response.status_code == 400


def test_update_unsupported_provider_returns_structured_400(client, auth_headers):
    # Real (unmocked) validate_provider_connection rejects any provider not in the registry.
    response = client.put(
        "/embedding-settings/made-up-provider",
        json={"model": "text-embedding-3", "api_key": "secret", "dimensions": 1536},
        headers=auth_headers("embedding_settings:write"),
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "embedding_provider"


def test_update_voyage_without_api_key_returns_structured_400(client, auth_headers):
    # Real (unmocked) validate_provider_connection: voyage requires an api_key. No prior config
    # exists for this provider, so the blank-api-key-keeps-existing fallback finds nothing to
    # reuse either — this is a genuinely missing key, not an omitted-on-purpose one.
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderSettingsRepository.get",
        return_value=None,
    ):
        response = client.put(
            "/embedding-settings/voyage",
            json={"model": "voyage-3", "dimensions": 1024},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "api_key"


def test_update_ollama_without_api_key_accepted_by_schema(client, auth_headers):
    # Ollama is self-hosted/keyless — proves api_key is genuinely optional end-to-end at the HTTP
    # layer, not just required-with-empty-string.
    with (
        patch(
            "app.presentation.routes.embedding_settings.EmbeddingProviderSettingsRepository.get",
            return_value=None,
        ),
        patch(
            "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.update_config",
            return_value=_status("ollama", configured=True),
        ),
    ):
        response = client.put(
            "/embedding-settings/ollama",
            json={"model": "nomic-embed-text", "dimensions": 768},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["configured"] is True
    assert body["base_url"] == "http://ollama:11434"


def test_update_model_locked_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.update_config",
        side_effect=ValidationError("embedding_model_locked", "documents exist", field="model"),
    ):
        response = client.put(
            "/embedding-settings/voyage",
            json={"model": "voyage-3", "api_key": "secret", "dimensions": 1024},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embedding_model_locked"


def test_update_bad_chunking_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.update_config",
        side_effect=ValidationError("validation_error", "bad chunking", field="chunk_overlap"),
    ):
        response = client.put(
            "/embedding-settings/voyage",
            json={
                "model": "voyage-3",
                "api_key": "secret",
                "dimensions": 1024,
                "chunk_size": 10,
                "chunk_overlap": 20,
            },
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "chunk_overlap"


def test_update_blank_api_key_keeps_the_existing_one(client, auth_headers):
    # GET /embedding-settings never returns the saved key (only `configured`), so a caller has no
    # way to round-trip it — omitting api_key must reuse whatever is already saved, not clear it.
    existing = type("Existing", (), {"api_key": "previously-saved-secret"})()
    with (
        patch(
            "app.presentation.routes.embedding_settings.EmbeddingProviderSettingsRepository.get",
            return_value=existing,
        ),
        patch(
            "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.update_config",
            return_value=_status("voyage", configured=True),
        ) as mock_update,
    ):
        response = client.put(
            "/embedding-settings/voyage",
            json={"model": "voyage-3", "dimensions": 1024},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    mock_update.assert_called_once_with("voyage", "voyage-3", "previously-saved-secret", None, 1024, 800, 100)


def test_update_success_returns_configured_true(client, auth_headers):
    with (
        patch(
            "app.presentation.routes.embedding_settings.EmbeddingProviderSettingsRepository.get",
            return_value=None,
        ),
        patch(
            "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.update_config",
            return_value=_status("ollama", configured=True),
        ),
    ):
        response = client.put(
            "/embedding-settings/ollama",
            json={"model": "nomic-embed-text", "dimensions": 768},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    assert response.get_json()["configured"] is True


def test_enable_returns_updated_status(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.enable",
        return_value=_status("ollama", enabled=True, configured=True),
    ) as mock_enable:
        response = client.post(
            "/embedding-settings/ollama/enable", headers=auth_headers("embedding_settings:write")
        )

    assert response.status_code == 200
    assert response.get_json()["enabled"] is True
    mock_enable.assert_called_once_with("ollama")


def test_enable_not_configured_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.enable",
        side_effect=ValidationError("embeddings_not_configured", "configure it first", field="provider"),
    ):
        response = client.post(
            "/embedding-settings/voyage/enable", headers=auth_headers("embedding_settings:write")
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embeddings_not_configured"


def test_enable_locked_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.enable",
        side_effect=ValidationError("embedding_model_locked", "documents exist", field="provider"),
    ):
        response = client.post(
            "/embedding-settings/voyage/enable", headers=auth_headers("embedding_settings:write")
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embedding_model_locked"


def test_disable_returns_updated_status(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.disable",
        return_value=_status("ollama", configured=True),
    ) as mock_disable:
        response = client.post(
            "/embedding-settings/ollama/disable", headers=auth_headers("embedding_settings:write")
        )

    assert response.status_code == 200
    assert response.get_json()["enabled"] is False
    mock_disable.assert_called_once_with("ollama")


def test_disable_locked_returns_structured_400(client, auth_headers):
    with patch(
        "app.presentation.routes.embedding_settings.EmbeddingProviderConfigService.disable",
        side_effect=ValidationError("embedding_model_locked", "documents exist", field="provider"),
    ):
        response = client.post(
            "/embedding-settings/ollama/disable", headers=auth_headers("embedding_settings:write")
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embedding_model_locked"


def test_missing_auth_returns_401(client):
    response = client.get("/embedding-settings")
    assert response.status_code == 401


def test_missing_write_scope_returns_403(client, auth_headers):
    response = client.put(
        "/embedding-settings/voyage",
        json={"model": "voyage-3", "api_key": "secret", "dimensions": 1024},
        headers=auth_headers("embedding_settings:read"),
    )
    assert response.status_code == 403
