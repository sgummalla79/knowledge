from __future__ import annotations

from uuid import UUID

from api.domain.entities import IngestionJob as IngestionJobEntity
from api.infrastructure.orm import IngestionJob as IngestionJobModel


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

    def list_by_org(self, org_id: UUID, limit: int, offset: int) -> list[IngestionJobEntity]:
        models = (
            self._session.query(IngestionJobModel)
            .filter(IngestionJobModel.org_id == org_id)
            .order_by(IngestionJobModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_to_entity(model) for model in models]

    def update_status(self, job_id: UUID, status: str, **fields) -> IngestionJobEntity:
        model = self._session.get(IngestionJobModel, job_id)
        model.status = status
        for key, value in fields.items():
            setattr(model, key, value)
        self._session.flush()
        return _to_entity(model)

    def commit(self) -> None:
        """Durably commits whatever's pending on this session -- specifically for callers (see
        DocumentService.start_ingestion/start_retry/start_crawl) that hand a job row off to a
        background thread with its own independent session immediately after create(), which only
        flushes. Without an explicit commit here first, that other session's own transaction
        (READ COMMITTED) can't see the row yet and update_status() fails looking it up."""
        self._session.commit()
