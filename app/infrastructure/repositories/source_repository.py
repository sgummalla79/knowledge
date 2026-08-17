from __future__ import annotations

from uuid import UUID

from app.domain.entities import Source as SourceEntity
from app.infrastructure.orm import Source as SourceModel


def _to_entity(model: SourceModel) -> SourceEntity:
    return SourceEntity(
        id=model.id,
        org_id=model.org_id,
        type=model.type,
        name=model.name,
        config=model.config,
        api_key_hash=model.api_key_hash,
        status=model.status,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
        last_synced_at=model.last_synced_at,
    )


class SourceRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, type: str, name: str, **fields) -> SourceEntity:
        model = SourceModel(org_id=org_id, type=type, name=name, **fields)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get(self, source_id: UUID) -> SourceEntity | None:
        model = self._session.get(SourceModel, source_id)
        return _to_entity(model) if model is not None else None

    def list_by_org(self, org_id: UUID) -> list[SourceEntity]:
        models = self._session.query(SourceModel).filter(SourceModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]
