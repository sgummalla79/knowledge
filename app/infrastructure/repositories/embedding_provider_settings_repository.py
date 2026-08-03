from sqlalchemy import func

from app.domain.entities import EmbeddingProviderConfig
from app.infrastructure.orm import EmbeddingProviderSetting


def _to_entity(model: EmbeddingProviderSetting) -> EmbeddingProviderConfig:
    return EmbeddingProviderConfig(
        id=model.id,
        provider=model.provider,
        enabled=model.enabled,
        model=model.model,
        api_key=model.api_key,
        base_url=model.base_url,
        dimensions=model.dimensions,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class EmbeddingProviderSettingsRepository:
    def __init__(self, session):
        self._session = session

    def list(self) -> list[EmbeddingProviderConfig]:
        rows = self._session.query(EmbeddingProviderSetting).order_by(EmbeddingProviderSetting.provider).all()
        return [_to_entity(row) for row in rows]

    def get(self, provider: str) -> EmbeddingProviderConfig | None:
        row = self._session.query(EmbeddingProviderSetting).filter_by(provider=provider).first()
        return _to_entity(row) if row is not None else None

    def upsert_config(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> EmbeddingProviderConfig:
        existing = self._session.query(EmbeddingProviderSetting).filter_by(provider=provider).first()
        if existing is None:
            existing = EmbeddingProviderSetting(provider=provider, enabled=False)
            self._session.add(existing)
        existing.model = model
        existing.api_key = api_key
        existing.base_url = base_url
        existing.dimensions = dimensions
        existing.chunk_size = chunk_size
        existing.chunk_overlap = chunk_overlap
        if existing.created_at is None:
            existing.created_at = func.now()
        self._session.flush()
        return _to_entity(existing)

    def set_enabled(self, provider: str, enabled: bool) -> EmbeddingProviderConfig:
        existing = self._session.query(EmbeddingProviderSetting).filter_by(provider=provider).first()
        if existing is None:
            existing = EmbeddingProviderSetting(provider=provider, enabled=enabled)
            self._session.add(existing)
        else:
            existing.enabled = enabled
        self._session.flush()
        return _to_entity(existing)
