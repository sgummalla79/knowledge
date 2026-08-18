from app.domain.entities import EmbeddingSettings as EmbeddingSettingsEntity
from app.infrastructure.orm import EmbeddingModel


class EmbeddingSettingsRepository:
    """Read-only view of whichever model is currently the org's default — ingestion and retrieval
    only ever need "the active settings", never the full per-provider config/toggle machinery (see
    EmbeddingProviderSettingsRepository for that)."""

    def __init__(self, session):
        self._session = session

    def get(self, org_id) -> EmbeddingSettingsEntity | None:
        row = (
            self._session.query(EmbeddingModel)
            .filter(EmbeddingModel.org_id == org_id, EmbeddingModel.is_default.is_(True))
            .first()
        )
        if row is None:
            return None
        return EmbeddingSettingsEntity(
            id=row.id,
            provider=row.provider,
            model=row.model_identifier,
            api_key=row.api_key,
            base_url=row.endpoint_url,
            dimensions=row.dimensions,
            chunk_size=row.chunk_size,
            chunk_overlap=row.chunk_overlap,
            created_at=row.created_at,
            updated_at=row.last_modified_at,
        )
