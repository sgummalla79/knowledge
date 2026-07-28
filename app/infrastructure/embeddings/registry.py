from app.constants import DEFAULT_OLLAMA_BASE_URL
from app.infrastructure.embeddings.ollama_provider import OllamaEmbeddingProvider
from app.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider

_PROVIDER_FACTORIES = {
    "voyage": lambda model, api_key, base_url: VoyageEmbeddingProvider(api_key=api_key, model=model),
    "ollama": lambda model, api_key, base_url: OllamaEmbeddingProvider(
        base_url=base_url or DEFAULT_OLLAMA_BASE_URL, model=model
    ),
}


class UnsupportedEmbeddingProviderError(ValueError):
    pass


class EmbeddingProviderRegistry:
    @staticmethod
    def resolve(provider: str, model: str, api_key: str | None, base_url: str | None = None):
        factory = _PROVIDER_FACTORIES.get(provider)
        if factory is None:
            raise UnsupportedEmbeddingProviderError(f"No embedding provider registered for '{provider}'")
        return factory(model, api_key, base_url)
