from unittest.mock import MagicMock, patch

import pytest

from api.application.embedding_model_listing_service import EmbeddingModelListingService
from api.domain import error_codes
from api.domain.errors import ValidationError
from api.infrastructure.embeddings.base import SupportsModelListing


def _mock_provider():
    # spec=SupportsModelListing is required, not cosmetic: a bare MagicMock() has every attribute
    # auto-vivified (hasattr() is always True), but isinstance() against a runtime_checkable
    # Protocol checks the *class*, and MagicMock's class doesn't declare list_models unless spec
    # tells it to — without spec, isinstance(MagicMock(), SupportsModelListing) is False even
    # though the mock plainly has a list_models attribute. Confirmed real provider classes
    # (OllamaEmbeddingProvider et al.) aren't affected — this is a Mock-only artifact.
    return MagicMock(spec=SupportsModelListing)


def test_list_models_returns_provider_models():
    service = EmbeddingModelListingService()
    provider_instance = _mock_provider()
    provider_instance.list_models.return_value = ["nomic-embed-text", "mxbai-embed-large"]

    with patch(
        "api.application.embedding_model_listing_service.EmbeddingProviderRegistry.resolve",
        return_value=provider_instance,
    ):
        result = service.list_models("ollama", None, "http://ollama:11434")

    assert result == ["nomic-embed-text", "mxbai-embed-large"]


def test_list_models_rejects_unsupported_provider():
    service = EmbeddingModelListingService()
    with pytest.raises(ValidationError) as exc_info:
        service.list_models("made-up-provider", "key", None)
    assert exc_info.value.code == error_codes.UNSUPPORTED_EMBEDDING_PROVIDER


def test_list_models_requires_api_key_when_provider_needs_one():
    service = EmbeddingModelListingService()
    with pytest.raises(ValidationError) as exc_info:
        service.list_models("voyage", None, None)
    assert exc_info.value.field == "api_key"


def test_list_models_rejects_provider_without_listing_capability():
    service = EmbeddingModelListingService()
    # No registry patch needed — voyage_provider.VoyageEmbeddingProvider genuinely has no
    # list_models method, so the real resolve() + isinstance check does the rejecting.
    with pytest.raises(ValidationError) as exc_info:
        service.list_models("voyage", "a-real-key", None)
    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LISTING_UNSUPPORTED


def test_list_models_wraps_provider_failure():
    service = EmbeddingModelListingService()
    provider_instance = _mock_provider()
    provider_instance.list_models.side_effect = RuntimeError("connection refused")

    with patch(
        "api.application.embedding_model_listing_service.EmbeddingProviderRegistry.resolve",
        return_value=provider_instance,
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.list_models("ollama", None, "http://ollama:11434")

    assert exc_info.value.code == error_codes.EMBEDDING_MODEL_LISTING_FAILED
