from app.constants import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL_DIMENSIONS,
    EMBEDDING_PROVIDERS_REQUIRING_API_KEY,
    SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER,
)
from app.domain import error_codes
from app.domain.errors import ValidationError


def validate_embedding_choice(provider: str, model: str, api_key: str | None = None) -> None:
    """Validation home for EmbeddingSettingsService's global embeddings key's provider/model."""
    supported_models = SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER.get(provider)
    if supported_models is None:
        raise ValidationError(
            error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
            f"Unsupported embedding provider '{provider}'.",
            field="embedding_provider",
        )
    if model not in supported_models:
        raise ValidationError(
            error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
            f"Unsupported embedding model '{model}' for provider '{provider}'.",
            field="embedding_model",
        )
    if EMBEDDING_MODEL_DIMENSIONS.get((provider, model)) != EMBEDDING_DIM:
        raise ValidationError(
            error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
            f"Model '{model}' is not compatible with this deployment's embedding dimension.",
            field="embedding_model",
        )
    if provider in EMBEDDING_PROVIDERS_REQUIRING_API_KEY and not api_key:
        raise ValidationError(
            error_codes.VALIDATION_ERROR,
            f"Provider '{provider}' requires an api_key.",
            field="api_key",
        )
