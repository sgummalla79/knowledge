from uuid import UUID

from api.domain.entities import IngestionJob
from api.domain.ports import DocumentRepositoryPort, IngestionJobRepositoryPort


class IngestionJobService:
    def __init__(self, repository: IngestionJobRepositoryPort, document_repo: DocumentRepositoryPort | None = None):
        self._repository = repository
        # Optional: only document_sizes_by_job() needs it.
        self._documents = document_repo

    def list_jobs(self, org_id: UUID, limit: int, offset: int) -> list[IngestionJob]:
        return self._repository.list_by_org(org_id, limit, offset)

    def document_sizes_by_job(self, jobs: list[IngestionJob]) -> dict[UUID, int]:
        """Maps job.id -> its linked document's size_bytes, for whichever jobs actually have one.

        ingestion_jobs carries no size column of its own -- documents.size_bytes already has this,
        so it's resolved here via one batched query instead of duplicating it onto a new column.
        document_id is only set on a job once it reaches a terminal state and (for a non-split
        upload) produced exactly one document -- see IngestionJobWorker._process_upload -- so a
        still-queued/processing job, or one split into multiple parts (document_ids, plural),
        simply won't appear in the returned mapping."""
        document_ids = [job.document_id for job in jobs if job.document_id is not None]
        if not document_ids:
            return {}
        size_by_document_id = {document.id: document.size_bytes for document in self._documents.list_by_ids(document_ids)}
        return {
            job.id: size_by_document_id[job.document_id]
            for job in jobs
            if job.document_id in size_by_document_id
        }
