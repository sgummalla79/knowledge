from uuid import UUID

from flask import Blueprint, jsonify, request

from app.application.document_service import DocumentService
from app.auth import require_scope
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.library_repository import LibraryRepository
from app.presentation.schemas import DocumentResponse, JobStatusResponse, PaginationQuery

documents_bp = Blueprint("documents", __name__, url_prefix="/libraries/<uuid:library_id>")


def _service() -> DocumentService:
    session = get_session()
    return DocumentService(DocumentRepository(session), LibraryRepository(session))


@documents_bp.post("/documents")
@require_scope("documents:write")
def upload_document(library_id: UUID):
    if "file" not in request.files:
        raise ValidationError(error_codes.VALIDATION_ERROR, "file is required", field="file")

    uploaded = request.files["file"]
    file_bytes = uploaded.read()
    job_id = _service().start_ingestion(library_id, uploaded.filename, file_bytes)
    return jsonify({"job_id": job_id}), 202


@documents_bp.get("/documents")
@require_scope("documents:read")
def list_documents(library_id: UUID):
    query = PaginationQuery.model_validate(request.args.to_dict())
    documents, total = _service().list_documents(library_id, query.limit, query.offset, query.sort)
    response = jsonify([DocumentResponse.from_entity(document).model_dump(mode="json") for document in documents])
    response.headers["X-Total-Count"] = str(total)
    return response


@documents_bp.get("/jobs/<job_id>")
@require_scope("documents:read")
def get_job(library_id: UUID, job_id: str):
    status = _service().get_job_status(job_id)
    return jsonify(JobStatusResponse(**status).model_dump())
