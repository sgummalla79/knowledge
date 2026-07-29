import pytest

from app.constants import DEFAULT_OLLAMA_BASE_URL
from app.infrastructure.embeddings.ollama_provider import OllamaEmbeddingProvider
from app.infrastructure.embeddings.openai_compatible_provider import OpenAICompatibleEmbeddingProvider
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry, UnsupportedEmbeddingProviderError
from app.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider


def test_resolve_voyage_returns_voyage_provider():
    provider = EmbeddingProviderRegistry.resolve("voyage", "voyage-3", "test-key")
    assert isinstance(provider, VoyageEmbeddingProvider)


def test_resolve_ollama_returns_ollama_provider():
    provider = EmbeddingProviderRegistry.resolve("ollama", "nomic-embed-text", None)
    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider._base_url == DEFAULT_OLLAMA_BASE_URL


def test_resolve_ollama_uses_explicit_base_url_override():
    provider = EmbeddingProviderRegistry.resolve(
        "ollama", "nomic-embed-text", None, base_url="http://custom-host:11434"
    )
    assert provider._base_url == "http://custom-host:11434"


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
    assert EmbeddingProviderRegistry.known_providers() == {"voyage", "ollama", "openai_compatible"}
