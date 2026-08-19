from flask import Blueprint, g, jsonify, request

from api.application.query_history_service import QueryHistoryService
from api.container import get_session
from api.infrastructure.repositories.query_repository import QueryRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import LimitOffsetQuery, QueryHistoryResponse

queries_bp = Blueprint("queries", __name__)


def _service() -> QueryHistoryService:
    return QueryHistoryService(QueryRepository(get_session()))


@queries_bp.get("/queries")
@require_org_session
def list_queries():
    query = LimitOffsetQuery.model_validate(request.args.to_dict())
    history = _service().list_history(g.org_id, query.limit, query.offset)
    return jsonify([QueryHistoryResponse.from_entity(item).model_dump(mode="json") for item in history])
