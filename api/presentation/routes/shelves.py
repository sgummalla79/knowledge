from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.shelf_service import ShelfService
from api.container import get_session
from api.domain import error_codes
from api.domain.entities import Shelf
from api.domain.errors import ForbiddenError, NotFoundError
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import (
    ShelfAccessRequest,
    ShelfCreateRequest,
    ShelfDocumentRequest,
    ShelfResponse,
    ShelfUpdateRequest,
)

shelves_bp = Blueprint("shelves", __name__)


def _service() -> ShelfService:
    return ShelfService(ShelfRepository(get_session()))


def _require_admin(org_id: UUID) -> None:
    # Checked against the specific org_id being acted on, not g.role — see orgs.py's identical
    # helper for why (g.role only reflects the session's currently *active* org).
    member = OrgMemberRepository(get_session()).get(org_id, g.user_id)
    if member is None or member.role != "admin":
        raise ForbiddenError("Only an org admin can manage shelf access.")


def _verify_document_ownership(org_id: UUID, document_id: UUID) -> None:
    # Both shelf-assignment routes and the reverse lookup below take a bare document_id with no
    # org in the path — without this, any org member could assign/list shelves for another org's
    # document by guessing its id.
    document = DocumentRepository(get_session()).get(document_id)
    if document is None or document.org_id != org_id:
        raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")


def _to_response(service: ShelfService, shelf: Shelf) -> ShelfResponse:
    return ShelfResponse.from_entity(shelf, service.document_count(shelf.id), service.member_count(shelf.id))


@shelves_bp.post("/shelves")
@require_org_session
def create_shelf():
    dto = ShelfCreateRequest.model_validate(request.get_json(silent=True) or {})
    shelf = _service().create_shelf(g.org_id, dto.name, dto.description)
    response = jsonify(ShelfResponse.from_entity(shelf, 0, 0).model_dump(mode="json"))
    response.status_code = 201
    response.headers["Location"] = f"/shelves/{shelf.id}"
    return response


@shelves_bp.get("/shelves")
@require_org_session
def list_shelves():
    service = _service()
    shelves = service.list_shelves(g.org_id)
    return jsonify([_to_response(service, shelf).model_dump(mode="json") for shelf in shelves])


@shelves_bp.get("/shelves/<uuid:shelf_id>")
@require_org_session
def get_shelf(shelf_id: UUID):
    service = _service()
    shelf = service.get_shelf(g.org_id, shelf_id)
    return jsonify(_to_response(service, shelf).model_dump(mode="json"))


@shelves_bp.patch("/shelves/<uuid:shelf_id>")
@require_org_session
def update_shelf(shelf_id: UUID):
    dto = ShelfUpdateRequest.model_validate(request.get_json(silent=True) or {})
    service = _service()
    shelf = service.update_shelf(g.org_id, shelf_id, dto.name, dto.description)
    return jsonify(_to_response(service, shelf).model_dump(mode="json"))


@shelves_bp.delete("/shelves/<uuid:shelf_id>")
@require_org_session
def delete_shelf(shelf_id: UUID):
    _service().delete_shelf(g.org_id, shelf_id)
    return "", 204


@shelves_bp.post("/shelves/<uuid:shelf_id>/documents")
@require_org_session
def add_document_to_shelf(shelf_id: UUID):
    dto = ShelfDocumentRequest.model_validate(request.get_json(silent=True) or {})
    _verify_document_ownership(g.org_id, dto.document_id)
    _service().add_document(g.org_id, shelf_id, dto.document_id)
    return "", 204


@shelves_bp.delete("/shelves/<uuid:shelf_id>/documents/<uuid:document_id>")
@require_org_session
def remove_document_from_shelf(shelf_id: UUID, document_id: UUID):
    _verify_document_ownership(g.org_id, document_id)
    _service().remove_document(g.org_id, shelf_id, document_id)
    return "", 204


@shelves_bp.post("/shelves/<uuid:shelf_id>/access")
@require_org_session
def grant_shelf_access(shelf_id: UUID):
    _require_admin(g.org_id)
    dto = ShelfAccessRequest.model_validate(request.get_json(silent=True) or {})
    _service().grant_access(g.org_id, shelf_id, dto.user_id, g.user_id)
    return "", 204


@shelves_bp.delete("/shelves/<uuid:shelf_id>/access/<uuid:user_id>")
@require_org_session
def revoke_shelf_access(shelf_id: UUID, user_id: UUID):
    _require_admin(g.org_id)
    _service().revoke_access(g.org_id, shelf_id, user_id)
    return "", 204


@shelves_bp.get("/documents/<uuid:document_id>/shelves")
@require_org_session
def list_document_shelves(document_id: UUID):
    _verify_document_ownership(g.org_id, document_id)
    service = _service()
    shelves = service.list_document_shelves(document_id)
    return jsonify([_to_response(service, shelf).model_dump(mode="json") for shelf in shelves])
