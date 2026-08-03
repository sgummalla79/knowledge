from app.domain.entities import EmbeddingSettings as EmbeddingSettingsEntity
from app.infrastructure.orm import EmbeddingProviderSetting


class EmbeddingSettingsRepository:
    """Read-only view of whichever provider is currently enabled — ingestion and retrieval only
    ever need "the active settings", never the full per-provider config/toggle machinery (see
    EmbeddingProviderSettingsRepository for that)."""

    def __init__(self, session):
        self._session = session

    def get(self) -> EmbeddingSettingsEntity | None:
        row = (
            self._session.query(EmbeddingProviderSetting)
            .filter(EmbeddingProviderSetting.enabled.is_(True))
            .first()
        )
        if row is None:
            return None
        return EmbeddingSettingsEntity(
            id=row.id,
            provider=row.provider,
            model=row.model,
            api_key=row.api_key,
            base_url=row.base_url,
            dimensions=row.dimensions,
            chunk_size=row.chunk_size,
            chunk_overlap=row.chunk_overlap,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
