from flask import Blueprint, g, jsonify, request

from api.application.ingestion_job_service import IngestionJobService
from api.container import get_session
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import IngestionJobResponse, LimitOffsetQuery

ingestion_jobs_bp = Blueprint("ingestion_jobs", __name__)


def _service() -> IngestionJobService:
    session = get_session()
    return IngestionJobService(IngestionJobRepository(session), DocumentRepository(session))


@ingestion_jobs_bp.get("/ingestion-jobs")
@require_org_session
def list_ingestion_jobs():
    query = LimitOffsetQuery.model_validate(request.args.to_dict())
    service = _service()
    jobs = service.list_jobs(g.org_id, query.limit, query.offset)
    sizes_by_job_id = service.document_sizes_by_job(jobs)
    return jsonify(
        [
            IngestionJobResponse.from_entity(job, size_bytes=sizes_by_job_id.get(job.id)).model_dump(mode="json")
            for job in jobs
        ]
    )
