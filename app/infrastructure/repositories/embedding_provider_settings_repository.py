from app.domain.entities import EmbeddingProviderToggle
from app.infrastructure.orm import EmbeddingProviderSetting


def _to_entity(model: EmbeddingProviderSetting) -> EmbeddingProviderToggle:
    return EmbeddingProviderToggle(
        id=model.id, provider=model.provider, enabled=model.enabled, updated_at=model.updated_at
    )


class EmbeddingProviderSettingsRepository:
    def __init__(self, session):
        self._session = session

    def list(self) -> list[EmbeddingProviderToggle]:
        rows = self._session.query(EmbeddingProviderSetting).order_by(EmbeddingProviderSetting.provider).all()
        return [_to_entity(row) for row in rows]

    def get_enabled_providers(self) -> set[str]:
        rows = self._session.query(EmbeddingProviderSetting).filter(EmbeddingProviderSetting.enabled.is_(True)).all()
        return {row.provider for row in rows}

    def set_enabled(self, provider: str, enabled: bool) -> EmbeddingProviderToggle:
        existing = self._session.query(EmbeddingProviderSetting).filter_by(provider=provider).first()
        if existing is None:
            existing = EmbeddingProviderSetting(provider=provider, enabled=enabled)
            self._session.add(existing)
        else:
            existing.enabled = enabled
        self._session.flush()
        return _to_entity(existing)
