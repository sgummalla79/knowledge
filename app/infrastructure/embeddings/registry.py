from app.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider

_PROVIDER_FACTORIES = {
    "voyage": lambda model, api_key: VoyageEmbeddingProvider(api_key=api_key, model=model),
}


class UnsupportedEmbeddingProviderError(ValueError):
    pass


class EmbeddingProviderRegistry:
    @staticmethod
    def resolve(provider: str, model: str, api_key: str):
        factory = _PROVIDER_FACTORIES.get(provider)
        if factory is None:
            raise UnsupportedEmbeddingProviderError(f"No embedding provider registered for '{provider}'")
        return factory(model, api_key)
