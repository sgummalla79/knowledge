from uuid import UUID

from flask import Blueprint, jsonify, request

from app.application.library_service import LibraryService
from app.auth import require_scope
from app.container import get_session
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.presentation.schemas import LibraryCreateRequest, LibraryResponse, LibraryUpdateRequest, PaginationQuery

libraries_bp = Blueprint("libraries", __name__, url_prefix="/libraries")


def _service() -> LibraryService:
    session = get_session()
    return LibraryService(CategoryRepository(session), EmbeddingSettingsRepository(session))


@libraries_bp.post("")
@require_scope("libraries:write")
def create_library():
    dto = LibraryCreateRequest.model_validate(request.get_json(silent=True) or {})
    library = _service().create_library(**dto.model_dump())
    response = jsonify(LibraryResponse.from_entity(library).model_dump(mode="json"))
    response.status_code = 201
    response.headers["Location"] = f"/libraries/{library.id}"
    return response


@libraries_bp.get("")
@require_scope("libraries:read")
def list_libraries():
    query = PaginationQuery.model_validate(request.args.to_dict())
    libraries, total = _service().list_libraries(query.limit, query.offset, query.sort)
    response = jsonify([LibraryResponse.from_entity(library).model_dump(mode="json") for library in libraries])
    response.headers["X-Total-Count"] = str(total)
    return response


@libraries_bp.get("/<uuid:library_id>")
@require_scope("libraries:read")
def get_library(library_id: UUID):
    library = _service().get_library(library_id)
    return jsonify(LibraryResponse.from_entity(library).model_dump(mode="json"))


@libraries_bp.patch("/<uuid:library_id>")
@require_scope("libraries:write")
def update_library(library_id: UUID):
    dto = LibraryUpdateRequest.model_validate(request.get_json(silent=True) or {})
    library = _service().update_library(library_id, **dto.model_dump())
    return jsonify(LibraryResponse.from_entity(library).model_dump(mode="json"))


@libraries_bp.delete("/<uuid:library_id>")
@require_scope("libraries:write")
def delete_library(library_id: UUID):
    _service().delete_library(library_id)
    return "", 204
