from app.config import config
from app.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider

_PROVIDER_FACTORIES = {
    "voyage": lambda model: VoyageEmbeddingProvider(api_key=config.voyage_api_key, model=model),
}


class UnsupportedEmbeddingProviderError(ValueError):
    pass


class EmbeddingProviderRegistry:
    @staticmethod
    def resolve(provider: str, model: str):
        factory = _PROVIDER_FACTORIES.get(provider)
        if factory is None:
            raise UnsupportedEmbeddingProviderError(f"No embedding provider registered for '{provider}'")
        return factory(model)
