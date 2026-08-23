import pytest

from api.infrastructure.embeddings.openai_compatible_provider import OpenAICompatibleEmbeddingProvider
from api.infrastructure.embeddings.registry import EmbeddingProviderRegistry, UnsupportedEmbeddingProviderError
from api.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider


def test_resolve_voyage_returns_voyage_provider():
    provider = EmbeddingProviderRegistry.resolve("voyage", "voyage-3", "test-key")
    assert isinstance(provider, VoyageEmbeddingProvider)


def test_resolve_unsupported_provider_raises():
    with pytest.raises(UnsupportedEmbeddingProviderError):
        EmbeddingProviderRegistry.resolve("made-up-provider", "text-embedding-3", "test-key")


def test_resolve_openai_compatible_returns_openai_compatible_provider():
    provider = EmbeddingProviderRegistry.resolve(
        "openai_compatible", "text-embedding-3-small", "test-key", base_url="https://api.openai.com/v1"
    )
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider._base_url == "https://api.openai.com/v1"


def test_known_providers_includes_all_registered_adapters():
    assert EmbeddingProviderRegistry.known_providers() == {"voyage", "openai_compatible"}


def test_supports_model_listing_true_for_openai_compatible():
    assert EmbeddingProviderRegistry.supports_model_listing("openai_compatible") is True


def test_supports_model_listing_false_for_voyage():
    # Voyage's SDK has no model-listing endpoint (voyageai==0.2.3 only exposes embed/rerank/
    # tokenizer/tokenize/count_tokens) — confirmed by inspecting the installed package.
    assert EmbeddingProviderRegistry.supports_model_listing("voyage") is False


def test_supports_model_listing_false_for_unknown_provider():
    assert EmbeddingProviderRegistry.supports_model_listing("made-up-provider") is False
