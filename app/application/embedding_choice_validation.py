from app.constants import SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER
from app.domain import error_codes
from app.domain.errors import ValidationError


def validate_embedding_choice(provider: str, model: str) -> None:
    """Shared by LibraryService (per-library choice) and EmbeddingSettingsService (the global
    embeddings key's provider/model) so the supported-provider/model check has one home."""
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
