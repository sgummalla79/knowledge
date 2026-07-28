import pytest

from app.constants import DEFAULT_OLLAMA_BASE_URL
from app.infrastructure.embeddings.ollama_provider import OllamaEmbeddingProvider
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
        EmbeddingProviderRegistry.resolve("openai", "text-embedding-3", "test-key")
