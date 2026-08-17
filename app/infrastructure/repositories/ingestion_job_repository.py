from __future__ import annotations

from uuid import UUID

from app.domain.entities import IngestionJob as IngestionJobEntity
from app.infrastructure.orm import IngestionJob as IngestionJobModel


def _to_entity(model: IngestionJobModel) -> IngestionJobEntity:
    return IngestionJobEntity(
        id=model.id,
        org_id=model.org_id,
        source_id=model.source_id,
        document_id=model.document_id,
        type=model.type,
        status=model.status,
        error_message=model.error_message,
        items_processed=model.items_processed,
        triggered_by=model.triggered_by,
        created_at=model.created_at,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )


class IngestionJobRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, type: str, **fields) -> IngestionJobEntity:
        model = IngestionJobModel(org_id=org_id, type=type, **fields)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get(self, job_id: UUID) -> IngestionJobEntity | None:
        model = self._session.get(IngestionJobModel, job_id)
        return _to_entity(model) if model is not None else None

    def list_by_org(self, org_id: UUID) -> list[IngestionJobEntity]:
        models = self._session.query(IngestionJobModel).filter(IngestionJobModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def update_status(self, job_id: UUID, status: str, **fields) -> IngestionJobEntity:
        model = self._session.get(IngestionJobModel, job_id)
        model.status = status
        for key, value in fields.items():
            setattr(model, key, value)
        self._session.flush()
        return _to_entity(model)
