from app.infrastructure.rerank.voyage_rerank_provider import VoyageRerankProvider

_PROVIDER_FACTORIES = {
    "voyage": lambda model, api_key: VoyageRerankProvider(api_key=api_key, model=model),
}


class UnsupportedRerankProviderError(ValueError):
    pass


class RerankProviderRegistry:
    @staticmethod
    def resolve(provider: str, model: str, api_key: str):
        factory = _PROVIDER_FACTORIES.get(provider)
        if factory is None:
            raise UnsupportedRerankProviderError(f"No rerank provider registered for '{provider}'")
        return factory(model, api_key)
