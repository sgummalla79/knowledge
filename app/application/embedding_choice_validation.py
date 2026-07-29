from app.constants import EMBEDDING_PROVIDERS_REQUIRING_API_KEY, EMBEDDING_PROVIDERS_REQUIRING_BASE_URL
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


def validate_embedding_choice(
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    dimensions: int,
    enabled_providers: set[str],
) -> None:
    """Validation home for EmbeddingSettingsService's global embeddings key's provider/model.

    Any provider registered in EmbeddingProviderRegistry is accepted with any model name/dimension
    the caller supplies — a new vendor is added by writing a provider class + registry entry, not
    by editing this whitelist. `enabled_providers` is a separate, admin-controlled toggle (see
    EmbeddingProviderSettingsService) — a provider can have working code and still be rejected
    here if an admin has switched it off."""
    if provider not in EmbeddingProviderRegistry.known_providers():
        raise ValidationError(
            error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
            f"Unsupported embedding provider '{provider}'.",
            field="embedding_provider",
        )
    if provider not in enabled_providers:
        raise ValidationError(
            error_codes.EMBEDDING_PROVIDER_DISABLED,
            f"Provider '{provider}' is currently disabled.",
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
