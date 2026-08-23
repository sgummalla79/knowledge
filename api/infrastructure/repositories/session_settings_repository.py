from uuid import UUID

from api.domain.entities import SessionSettings as SessionSettingsEntity
from api.infrastructure.orm import SessionSettings as SessionSettingsModel


def _to_entity(model: SessionSettingsModel) -> SessionSettingsEntity:
    return SessionSettingsEntity(
        org_id=model.org_id,
        inactivity_timeout_minutes=model.inactivity_timeout_minutes,
        last_modified_by=model.last_modified_by,
        last_modified_at=model.last_modified_at,
    )


class SessionSettingsRepository:
    def __init__(self, session):
        self._session = session

    def get(self, org_id: UUID) -> SessionSettingsEntity | None:
        model = self._session.get(SessionSettingsModel, org_id)
        return _to_entity(model) if model is not None else None

    def upsert(self, org_id: UUID, inactivity_timeout_minutes: int, modified_by: UUID | None) -> SessionSettingsEntity:
        model = self._session.get(SessionSettingsModel, org_id)
        if model is None:
            model = SessionSettingsModel(org_id=org_id)
            self._session.add(model)
        model.inactivity_timeout_minutes = inactivity_timeout_minutes
        model.last_modified_by = modified_by
        self._session.flush()
        return _to_entity(model)
