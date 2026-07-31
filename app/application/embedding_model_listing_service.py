from app.application.embedding_choice_validation import validate_provider_connection
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.domain.ports import EmbeddingProviderSettingsRepositoryPort
from app.infrastructure.embeddings.base import SupportsModelListing
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


class EmbeddingModelListingService:
    """Backs POST /embedding-options/models — lets a caller list a provider's live model catalog
    using credentials they've typed but not yet saved, so a UI can populate a dropdown before the
    user commits to PUT /embedding-settings."""

    def __init__(self, provider_settings_repo: EmbeddingProviderSettingsRepositoryPort):
        self._provider_settings = provider_settings_repo

    def list_models(self, provider: str, api_key: str | None, base_url: str | None) -> list[str]:
        validate_provider_connection(
            provider, api_key, base_url, self._provider_settings.get_enabled_providers()
        )

        # No model has been chosen yet — that's the whole point of this endpoint — so resolve()
        # is given a placeholder that's never actually used (list_models() never touches self._model).
        provider_instance = EmbeddingProviderRegistry.resolve(provider, "", api_key, base_url)
        if not isinstance(provider_instance, SupportsModelListing):
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LISTING_UNSUPPORTED,
                f"Provider '{provider}' does not support live model listing.",
                field="provider",
            )

        try:
            return provider_instance.list_models()
        except Exception as error:
            raise ValidationError(
                error_codes.EMBEDDING_MODEL_LISTING_FAILED,
                f"Could not list models for provider '{provider}': {error}",
                field="provider",
            ) from error
