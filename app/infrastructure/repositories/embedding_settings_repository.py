from app.domain.entities import EmbeddingSettings as EmbeddingSettingsEntity
from app.infrastructure.orm import EmbeddingSettings as EmbeddingSettingsModel


def _to_entity(model: EmbeddingSettingsModel) -> EmbeddingSettingsEntity:
    return EmbeddingSettingsEntity(
        id=model.id,
        provider=model.provider,
        model=model.model,
        api_key=model.api_key,
        base_url=model.base_url,
        dimensions=model.dimensions,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class EmbeddingSettingsRepository:
    """Single global row — application-level singleton (no DB constraint needed at this scale)."""

    def __init__(self, session):
        self._session = session

    def get(self) -> EmbeddingSettingsEntity | None:
        model = self._session.query(EmbeddingSettingsModel).first()
        return _to_entity(model) if model is not None else None

    def upsert(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
        base_url: str | None = None,
    ) -> EmbeddingSettingsEntity:
        existing = self._session.query(EmbeddingSettingsModel).first()
        if existing is None:
            existing = EmbeddingSettingsModel(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                dimensions=dimensions,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            self._session.add(existing)
        else:
            existing.provider = provider
            existing.model = model
            existing.api_key = api_key
            existing.base_url = base_url
            existing.dimensions = dimensions
            existing.chunk_size = chunk_size
            existing.chunk_overlap = chunk_overlap
        self._session.flush()
        return _to_entity(existing)

    def clear(self) -> None:
        existing = self._session.query(EmbeddingSettingsModel).first()
        if existing is not None:
            self._session.delete(existing)
            self._session.flush()
