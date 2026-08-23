from unittest.mock import patch

from uuid import uuid4

import pytest

from api import create_app
from api.domain.errors import ValidationError

# HTTP-layer only — EmbeddingModelListingService is mocked. Real listing/validation behavior is
# covered by tests/unit/test_embedding_model_listing_service.py.


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
        sess["csrf_token"] = "test-csrf-token"
    test_client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
    return test_client


def test_list_models_returns_models(client):
    with patch(
        "api.presentation.routes.options.EmbeddingModelListingService.list_models",
        return_value=["nomic-embed-text", "mxbai-embed-large"]
    ) as mock_list_models:
        response = client.post(
            "/embedding-options/models",
            json={"provider": "openai_compatible", "base_url": "https://api.example.com/v1"}
        )

    assert response.status_code == 200
    assert response.get_json() == {"models": ["nomic-embed-text", "mxbai-embed-large"]}
    mock_list_models.assert_called_once_with("openai_compatible", None, "https://api.example.com/v1")


def test_list_models_propagates_validation_error(client):
    with patch(
        "api.presentation.routes.options.EmbeddingModelListingService.list_models",
        side_effect=ValidationError(
            "embedding_model_listing_unsupported", "not supported", field="provider"
        )
    ):
        response = client.post(
            "/embedding-options/models",
            json={"provider": "voyage", "api_key": "a-key"}
        )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "embedding_model_listing_unsupported"


def test_list_models_missing_provider_rejected_by_schema(client):
    response = client.post(
        "/embedding-options/models",
        json={}
    )
    assert response.status_code == 400
