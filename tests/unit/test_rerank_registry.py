import pytest

from app.infrastructure.rerank.registry import RerankProviderRegistry, UnsupportedRerankProviderError
from app.infrastructure.rerank.voyage_rerank_provider import VoyageRerankProvider


def test_resolve_voyage_returns_voyage_provider():
    provider = RerankProviderRegistry.resolve("voyage", "rerank-2", "test-key")
    assert isinstance(provider, VoyageRerankProvider)


def test_resolve_unsupported_provider_raises():
    with pytest.raises(UnsupportedRerankProviderError):
        RerankProviderRegistry.resolve("cohere", "rerank-v3", "test-key")
