from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.category_service import CategoryService
from api.container import get_session
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import CategoryCreateRequest, CategoryResponse, CategoryUpdateRequest

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


def _service() -> CategoryService:
    session = get_session()
    return CategoryService(CategoryRepository(session), EmbeddingSettingsRepository(session))


@categories_bp.post("")
@require_org_session
def create_category():
    dto = CategoryCreateRequest.model_validate(request.get_json(silent=True) or {})
    category = _service().create_category(g.org_id, **dto.model_dump())
    response = jsonify(CategoryResponse.from_entity(category).model_dump(mode="json"))
    response.status_code = 201
    response.headers["Location"] = f"/categories/{category.id}"
    return response


@categories_bp.get("")
@require_org_session
def list_categories():
    categories = _service().list_categories(g.org_id)
    return jsonify([CategoryResponse.from_entity(category).model_dump(mode="json") for category in categories])


@categories_bp.get("/<uuid:category_id>")
@require_org_session
def get_category(category_id: UUID):
    category = _service().get_category(g.org_id, category_id)
    return jsonify(CategoryResponse.from_entity(category).model_dump(mode="json"))


@categories_bp.patch("/<uuid:category_id>")
@require_org_session
def update_category(category_id: UUID):
    dto = CategoryUpdateRequest.model_validate(request.get_json(silent=True) or {})
    category = _service().update_category(g.org_id, category_id, **dto.model_dump())
    return jsonify(CategoryResponse.from_entity(category).model_dump(mode="json"))


@categories_bp.delete("/<uuid:category_id>")
@require_org_session
def delete_category(category_id: UUID):
    _service().delete_category(g.org_id, category_id)
    return "", 204
