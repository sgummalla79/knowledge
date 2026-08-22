from flask import Blueprint, g, jsonify, request

from api.application.ingestion_job_service import IngestionJobService
from api.container import get_session
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import IngestionJobResponse, LimitOffsetQuery

ingestion_jobs_bp = Blueprint("ingestion_jobs", __name__)


def _service() -> IngestionJobService:
    return IngestionJobService(IngestionJobRepository(get_session()))


@ingestion_jobs_bp.get("/ingestion-jobs")
@require_org_session
def list_ingestion_jobs():
    query = LimitOffsetQuery.model_validate(request.args.to_dict())
    jobs = _service().list_jobs(g.org_id, query.limit, query.offset)
    return jsonify([IngestionJobResponse.from_entity(job).model_dump(mode="json") for job in jobs])
