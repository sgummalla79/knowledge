from app.domain.entities import RouterSettings as RouterSettingsEntity
from app.infrastructure.orm import RouterSettings as RouterSettingsModel


def _to_entity(model: RouterSettingsModel) -> RouterSettingsEntity:
    return RouterSettingsEntity(
        top_n=model.top_n,
        min_similarity=model.min_similarity,
        updated_at=model.updated_at,
    )


class RouterSettingsRepository:
    """Single global row — application-level singleton (mirrors SearchSettingsRepository).

    An absent row is not an error state: RouterSettingsService fills in defaults when get()
    returns None, so callers always have usable values.
    """

    def __init__(self, session):
        self._session = session

    def get(self) -> RouterSettingsEntity | None:
        model = self._session.query(RouterSettingsModel).first()
        return _to_entity(model) if model is not None else None

    def upsert(self, top_n: int, min_similarity: float) -> RouterSettingsEntity:
        existing = self._session.query(RouterSettingsModel).first()
        if existing is None:
            existing = RouterSettingsModel(top_n=top_n, min_similarity=min_similarity)
            self._session.add(existing)
        else:
            existing.top_n = top_n
            existing.min_similarity = min_similarity
        self._session.flush()
        return _to_entity(existing)
