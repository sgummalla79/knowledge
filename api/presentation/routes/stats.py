from flask import Blueprint, g, jsonify

from api.application.stats_service import StatsService
from api.container import get_session
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import DashboardStatsResponse

stats_bp = Blueprint("stats", __name__, url_prefix="/stats")


def _service() -> StatsService:
    session = get_session()
    return StatsService(DocumentRepository(session), ChunkRepository(session), QueryRepository(session))


@stats_bp.get("/dashboard")
@require_org_session
def get_dashboard_stats():
    stats = _service().get_dashboard_stats(g.org_id)
    return jsonify(DashboardStatsResponse.from_entity(stats).model_dump(mode="json"))
