from __future__ import annotations

from datetime import datetime, timezone
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
        category_id=model.category_id,
        payload_filename=model.payload_filename,
        crawl_url=model.crawl_url,
        crawl_max_pages=model.crawl_max_pages,
        crawl_scope_prefix=model.crawl_scope_prefix,
        cancel_requested=model.cancel_requested,
        parts_total=model.parts_total,
        parts_completed=model.parts_completed,
        parts_failed=model.parts_failed,
        document_ids=list(model.document_ids),
        pages=dict(model.pages),
        claimed_at=model.claimed_at,
        claimed_by=model.claimed_by,
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

    # --- Release 1 of the standalone-worker migration (see migration 0018) ---
    # Not yet called from any live request path -- these back api/ingestion_worker/ only.

    def claim_next_queued(self, worker_id: str) -> IngestionJobEntity | None:
        """Atomically claims the oldest queued row via FOR UPDATE SKIP LOCKED -- the standard
        Postgres work-queue pattern: a concurrent claimer's already-locked row is skipped rather
        than blocked on, so multiple worker replicas can safely claim different rows in parallel
        without ever double-processing the same one.

        Commits immediately, unlike this repository's other write methods (which leave committing
        to the caller) -- the claim must be durable and the row's lock released the instant this
        call returns, not held open for however long the caller then spends actually processing
        the job."""
        model = (
            self._session.query(IngestionJobModel)
            .filter(IngestionJobModel.status == "queued")
            .order_by(IngestionJobModel.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
            .first()
        )
        if model is None:
            return None
        now = datetime.now(timezone.utc)
        model.status = "processing"
        model.claimed_at = now
        model.claimed_by = worker_id
        model.started_at = now
        self._session.commit()
        return _to_entity(model)

    def is_cancellation_requested(self, job_id: UUID) -> bool:
        """Cheap poll query -- same semantics as JobStore.is_cancellation_requested, backed by a
        row instead of a dict. Called between embedding batches (low frequency), so a plain SELECT
        is enough; no caching needed."""
        model = self._session.get(IngestionJobModel, job_id)
        return model is not None and model.cancel_requested

    def get_payload(self, job_id: UUID) -> bytes | None:
        """Explicit accessor for the deferred payload column -- mirrors
        DocumentRepository.get_raw_bytes, same reasoning: never loaded implicitly by get()/
        list_by_org(), only when a caller (the worker) actually needs the uploaded bytes."""
        model = self._session.get(IngestionJobModel, job_id)
        return model.payload if model is not None else None

    def clear_payload(self, job_id: UUID) -> None:
        """Reclaims the stored upload bytes once the worker has read them -- this table never
        needs to hold an upload's payload for longer than it takes to process the job."""
        model = self._session.get(IngestionJobModel, job_id)
        if model is not None:
            model.payload = None
            self._session.flush()

    def set_parts_total(self, job_id: UUID, parts_total: int) -> None:
        model = self._session.get(IngestionJobModel, job_id)
        model.parts_total = parts_total
        self._session.flush()

    def increment_parts_completed(self, job_id: UUID, document_id: UUID) -> None:
        model = self._session.get(IngestionJobModel, job_id)
        model.document_ids = [*model.document_ids, str(document_id)]
        model.parts_completed += 1
        self._session.flush()

    def increment_parts_failed(self, job_id: UUID) -> None:
        model = self._session.get(IngestionJobModel, job_id)
        model.parts_failed += 1
        self._session.flush()

    def set_page_status(
        self, job_id: UUID, url: str, status: str, document_id: UUID | None, error: str | None
    ) -> None:
        model = self._session.get(IngestionJobModel, job_id)
        model.pages = {
            **model.pages,
            url: {"status": status, "document_id": str(document_id) if document_id else None, "error": error},
        }
        self._session.flush()
