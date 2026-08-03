from app.constants import EMBEDDING_PROVIDERS_REQUIRING_API_KEY, EMBEDDING_PROVIDERS_REQUIRING_BASE_URL
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


def validate_provider_connection(provider: str, api_key: str | None, base_url: str | None) -> None:
    """The structural checks shared by every flow that needs to talk to a provider before a model
    has even been chosen (saving a provider's config, or listing that provider's live models): is
    it a real registered provider, and does the caller have whatever credentials that provider
    needs. Any registered provider is accepted with any model name/dimensions the caller
    supplies — a new vendor is added by writing a provider class + registry entry, not by editing
    this whitelist."""
    if provider not in EmbeddingProviderRegistry.known_providers():
        raise ValidationError(
            error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
            f"Unsupported embedding provider '{provider}'.",
            field="embedding_provider",
        )
    if provider in EMBEDDING_PROVIDERS_REQUIRING_API_KEY and not api_key:
        raise ValidationError(
            error_codes.VALIDATION_ERROR,
            f"Provider '{provider}' requires an api_key.",
            field="api_key",
        )
    if provider in EMBEDDING_PROVIDERS_REQUIRING_BASE_URL and not base_url:
        raise ValidationError(
            error_codes.VALIDATION_ERROR,
            f"Provider '{provider}' requires a base_url.",
            field="base_url",
        )
