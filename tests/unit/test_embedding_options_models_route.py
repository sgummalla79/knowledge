from unittest.mock import patch

import pytest

from app import create_app
from app.domain.errors import ValidationError

# HTTP-layer only — EmbeddingModelListingService is mocked. Real listing/validation behavior is
# covered by tests/unit/test_embedding_model_listing_service.py.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_list_models_returns_models(client, auth_headers):
    with patch(
        "app.presentation.routes.options.EmbeddingModelListingService.list_models",
        return_value=["nomic-embed-text", "mxbai-embed-large"],
    ) as mock_list_models:
        response = client.post(
            "/embedding-options/models",
            json={"provider": "ollama", "base_url": "http://ollama:11434"},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 200
    assert response.get_json() == {"models": ["nomic-embed-text", "mxbai-embed-large"]}
    mock_list_models.assert_called_once_with("ollama", None, "http://ollama:11434")


def test_list_models_propagates_validation_error(client, auth_headers):
    with patch(
        "app.presentation.routes.options.EmbeddingModelListingService.list_models",
        side_effect=ValidationError(
            "embedding_model_listing_unsupported", "not supported", field="provider"
        ),
    ):
        response = client.post(
            "/embedding-options/models",
            json={"provider": "voyage", "api_key": "a-key"},
            headers=auth_headers("embedding_settings:write"),
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embedding_model_listing_unsupported"


def test_list_models_missing_provider_rejected_by_schema(client, auth_headers):
    response = client.post(
        "/embedding-options/models",
        json={},
        headers=auth_headers("embedding_settings:write"),
    )
    assert response.status_code == 400


def test_list_models_requires_write_scope(client, auth_headers):
    response = client.post(
        "/embedding-options/models",
        json={"provider": "ollama", "base_url": "http://ollama:11434"},
        headers=auth_headers("embedding_settings:read"),
    )
    assert response.status_code == 403


def test_list_models_requires_auth(client):
    response = client.post("/embedding-options/models", json={"provider": "ollama"})
    assert response.status_code == 401
