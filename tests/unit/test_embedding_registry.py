import pytest

from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry, UnsupportedEmbeddingProviderError
from app.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider


def test_resolve_voyage_returns_voyage_provider():
    provider = EmbeddingProviderRegistry.resolve("voyage", "voyage-3")
    assert isinstance(provider, VoyageEmbeddingProvider)


def test_resolve_unsupported_provider_raises():
    with pytest.raises(UnsupportedEmbeddingProviderError):
        EmbeddingProviderRegistry.resolve("openai", "text-embedding-3")
