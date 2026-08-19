from uuid import UUID

from flask import Blueprint, g, jsonify, request

from api.application.tag_service import TagService
from api.container import get_session
from api.domain import error_codes
from api.domain.errors import NotFoundError
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.tag_repository import TagRepository
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import DocumentTagRequest, TagCreateRequest, TagResponse

tags_bp = Blueprint("tags", __name__)


def _service() -> TagService:
    return TagService(TagRepository(get_session()))


def _verify_document_ownership(org_id: UUID, document_id: UUID) -> None:
    # These routes take a bare document_id with no org in the path — without this check, any org
    # member could tag/untag/list tags on another org's document by guessing its id.
    document = DocumentRepository(get_session()).get(document_id)
    if document is None or document.org_id != org_id:
        raise NotFoundError(error_codes.DOCUMENT_NOT_FOUND, "Document not found.")


@tags_bp.post("/tags")
@require_org_session
def create_tag():
    dto = TagCreateRequest.model_validate(request.get_json(silent=True) or {})
    tag = _service().create_tag(g.org_id, dto.name)
    response = jsonify(TagResponse.from_entity(tag).model_dump(mode="json"))
    response.status_code = 201
    response.headers["Location"] = f"/tags/{tag.id}"
    return response


@tags_bp.get("/tags")
@require_org_session
def list_tags():
    tags = _service().list_tags(g.org_id)
    return jsonify([TagResponse.from_entity(tag).model_dump(mode="json") for tag in tags])


@tags_bp.post("/documents/<uuid:document_id>/tags")
@require_org_session
def tag_document(document_id: UUID):
    _verify_document_ownership(g.org_id, document_id)
    dto = DocumentTagRequest.model_validate(request.get_json(silent=True) or {})
    _service().tag_document(g.org_id, document_id, dto.tag_id)
    return "", 204


@tags_bp.delete("/documents/<uuid:document_id>/tags/<uuid:tag_id>")
@require_org_session
def untag_document(document_id: UUID, tag_id: UUID):
    _verify_document_ownership(g.org_id, document_id)
    _service().untag_document(g.org_id, document_id, tag_id)
    return "", 204


@tags_bp.get("/documents/<uuid:document_id>/tags")
@require_org_session
def list_document_tags(document_id: UUID):
    _verify_document_ownership(g.org_id, document_id)
    tags = _service().list_document_tags(document_id)
    return jsonify([TagResponse.from_entity(tag).model_dump(mode="json") for tag in tags])
