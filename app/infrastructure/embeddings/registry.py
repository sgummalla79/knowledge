from app.constants import DEFAULT_OLLAMA_BASE_URL
from app.infrastructure.embeddings.base import SupportsModelListing
from app.infrastructure.embeddings.ollama_provider import OllamaEmbeddingProvider
from app.infrastructure.embeddings.openai_compatible_provider import OpenAICompatibleEmbeddingProvider
from app.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider

# Single source of truth for "which providers exist" — known_providers() and resolve() both key
# off this, so a provider can never be resolvable without also being a known provider (or vice
# versa).
_PROVIDER_CLASSES: dict[str, type] = {
    "voyage": VoyageEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "openai_compatible": OpenAICompatibleEmbeddingProvider,
}

_PROVIDER_FACTORIES = {
    "voyage": lambda model, api_key, base_url: VoyageEmbeddingProvider(api_key=api_key, model=model),
    "ollama": lambda model, api_key, base_url: OllamaEmbeddingProvider(
        base_url=base_url or DEFAULT_OLLAMA_BASE_URL, model=model
    ),
    "openai_compatible": lambda model, api_key, base_url: OpenAICompatibleEmbeddingProvider(
        base_url=base_url, api_key=api_key, model=model
    ),
}


class UnsupportedEmbeddingProviderError(ValueError):
    pass


class EmbeddingProviderRegistry:
    @staticmethod
    def known_providers() -> set[str]:
        return set(_PROVIDER_FACTORIES.keys())

    @staticmethod
    def supports_model_listing(provider: str) -> bool:
        """Structural check against the provider's class, not an instance — so callers (e.g.
        GET /embedding-options) can tell a UI whether "fetch models" is even worth offering for a
        provider before the caller has supplied any credentials to construct one."""
        provider_class = _PROVIDER_CLASSES.get(provider)
        return provider_class is not None and issubclass(provider_class, SupportsModelListing)

    @staticmethod
    def resolve(provider: str, model: str, api_key: str | None, base_url: str | None = None):
        factory = _PROVIDER_FACTORIES.get(provider)
        if factory is None:
            raise UnsupportedEmbeddingProviderError(f"No embedding provider registered for '{provider}'")
        return factory(model, api_key, base_url)
