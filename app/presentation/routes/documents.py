from uuid import UUID

from flask import Blueprint, jsonify, request

from app import container
from app.application.document_service import DocumentService
from app.constants import WEB_CRAWL_RATE_LIMIT
from app.container import get_session
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.presentation.schemas import (
    CrawlJobStatusResponse,
    CrawlRequest,
    DocumentRenameRequest,
    DocumentResponse,
    JobStatusResponse,
    PaginationQuery,
)
from app.rate_limit import limiter

documents_bp = Blueprint("documents", __name__)


def _service() -> DocumentService:
    session = get_session()
    return DocumentService(DocumentRepository(session), ChunkRepository(session))


@documents_bp.post("/documents")
def upload_document():
    if "file" not in request.files:
        raise ValidationError(error_codes.VALIDATION_ERROR, "file is required", field="file")

    uploaded = request.files["file"]
    file_bytes = uploaded.read()
    category_id = request.form.get("category_id")
    job_id = _service().start_ingestion(
        container.get_default_org_id(),
        container.get_default_user_id(),
        uploaded.filename,
        file_bytes,
        category_id=UUID(category_id) if category_id else None,
    )
    return jsonify({"job_id": job_id}), 202


@documents_bp.post("/documents/crawl")
@limiter.limit(WEB_CRAWL_RATE_LIMIT)
def crawl_documents():
    """Ingests one or more pages starting from a URL — max_pages=1 (the default) ingests just
    that page; a higher value crawls outward to in-scope linked pages (see WebCrawlService)."""
    dto = CrawlRequest.model_validate(request.get_json(silent=True) or {})
    job_id = _service().start_crawl(
        container.get_default_org_id(),
        container.get_default_user_id(),
        dto.url,
        dto.max_pages,
        dto.scope_prefix,
        category_id=dto.category_id,
    )
    return jsonify({"job_id": job_id}), 202


@documents_bp.get("/crawl-jobs/<job_id>")
def get_crawl_job(job_id: str):
    status = _service().get_crawl_job_status(job_id)
    return jsonify(CrawlJobStatusResponse(**status).model_dump())


@documents_bp.get("/documents")
def list_documents():
    query = PaginationQuery.model_validate(request.args.to_dict())
    documents, total = _service().list_documents(
        container.get_default_org_id(), query.limit, query.offset, query.sort
    )
    response = jsonify([DocumentResponse.from_entity(document).model_dump(mode="json") for document in documents])
    response.headers["X-Total-Count"] = str(total)
    return response


@documents_bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    status = _service().get_job_status(job_id)
    return jsonify(JobStatusResponse(**status).model_dump())


@documents_bp.post("/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    """Best-effort: cancellation is checked between embedding-provider batches, not instant — the
    job's status stays "running" (with cancel_requested now true, see JobStatusResponse) until it
    actually settles on "cancelled"."""
    _service().cancel_job(job_id)
    return "", 202


@documents_bp.delete("/documents/<uuid:document_id>")
def delete_document(document_id: UUID):
    _service().delete_document(container.get_default_org_id(), document_id)
    return "", 204


@documents_bp.patch("/documents/<uuid:document_id>")
def rename_document(document_id: UUID):
    dto = DocumentRenameRequest.model_validate(request.get_json(silent=True) or {})
    document = _service().rename_document(container.get_default_org_id(), document_id, dto.title)
    return jsonify(DocumentResponse.from_entity(document).model_dump(mode="json"))


@documents_bp.post("/documents/<uuid:document_id>/retry")
def retry_document(document_id: UUID):
    job_id = _service().start_retry(container.get_default_org_id(), document_id)
    return jsonify({"job_id": job_id}), 202
