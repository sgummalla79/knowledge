from app.constants import SUPPORTED_RERANK_MODELS_BY_PROVIDER
from app.domain import error_codes
from app.domain.errors import ValidationError


def validate_rerank_choice(provider: str, model: str) -> None:
    """Mirrors validate_embedding_choice — shared validation home for SearchSettingsService."""
    supported_models = SUPPORTED_RERANK_MODELS_BY_PROVIDER.get(provider)
    if supported_models is None:
        raise ValidationError(
            error_codes.UNSUPPORTED_RERANK_MODEL,
            f"Unsupported rerank provider '{provider}'.",
            field="rerank_provider",
        )
    if model not in supported_models:
        raise ValidationError(
            error_codes.UNSUPPORTED_RERANK_MODEL,
            f"Unsupported rerank model '{model}' for provider '{provider}'.",
            field="rerank_model",
        )
