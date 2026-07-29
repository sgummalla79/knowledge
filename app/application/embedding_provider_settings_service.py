from app.domain import error_codes
from app.domain.entities import EmbeddingProviderToggle
from app.domain.errors import ValidationError
from app.domain.ports import EmbeddingProviderSettingsRepositoryPort
from app.infrastructure.embeddings.registry import EmbeddingProviderRegistry


class EmbeddingProviderSettingsService:
    def __init__(self, repository: EmbeddingProviderSettingsRepositoryPort):
        self._repository = repository

    def list_providers(self) -> list[EmbeddingProviderToggle]:
        return self._repository.list()

    def set_enabled(self, provider: str, enabled: bool) -> EmbeddingProviderToggle:
        if provider not in EmbeddingProviderRegistry.known_providers():
            raise ValidationError(
                error_codes.UNSUPPORTED_EMBEDDING_PROVIDER,
                f"Unsupported embedding provider '{provider}'.",
                field="provider",
            )
        return self._repository.set_enabled(provider, enabled)
