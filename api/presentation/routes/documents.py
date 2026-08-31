from uuid import UUID, uuid4

from flask import Blueprint, g, jsonify, request

from api.application.document_service import DocumentService
from api.config import config
from api.constants import WEB_CRAWL_RATE_LIMIT
from api.container import get_session
from api.domain import error_codes
from api.domain.errors import ValidationError
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.infrastructure.storage.upload_storage import UploadStorage
from api.presentation.routes.app_auth import require_permission
from api.presentation.routes.auth_ui import require_org_session
from api.presentation.schemas import (
    ChunkResponse,
    CrawlJobStatusResponse,
    CrawlRequest,
    DocumentMetadataUpdateRequest,
    DocumentRenameRequest,
    DocumentResponse,
    JobStatusResponse,
    LimitOffsetQuery,
    PaginationQuery,
)
from api.rate_limit import limiter

documents_bp = Blueprint("documents", __name__)


def _service() -> DocumentService:
    session = get_session()
    return DocumentService(
        DocumentRepository(session), ChunkRepository(session), IngestionJobRepository(session), CategoryRepository(session)
    )


@documents_bp.post("/documents")
@require_permission("documents:write")
def upload_document():
    if "file" not in request.files:
        raise ValidationError(error_codes.VALIDATION_ERROR, "file is required", field="file")

    uploaded = request.files["file"]
    # Pre-generated here (not left to the DB default) since the on-disk path is derived from it,
    # and the file needs to land on disk before the job row referencing that path is created --
    # see DocumentService.start_ingestion's own docstring.
    job_id = uuid4()
    storage = UploadStorage(config.uploads_dir)
    payload_path = storage.path_for_job_upload(g.org_id, job_id)
    # FileStorage.save() streams from the WSGI request body straight to disk in chunks -- never
    # materializes the whole upload as one Python bytes object (see
    # docs/UPLOAD_STORAGE_REDESIGN.md).
    storage.save_stream(payload_path, uploaded)
    category_id = request.form.get("category_id")
    job_id_str = _service().start_ingestion(
        g.org_id,
        g.user_id,
        uploaded.filename,
        payload_path,
        job_id=job_id,
        category_id=UUID(category_id) if category_id else None,
    )
    return jsonify({"job_id": job_id_str}), 202


@documents_bp.post("/documents/crawl")
@require_permission("documents:write")
@limiter.limit(WEB_CRAWL_RATE_LIMIT)
def crawl_documents():
    """Ingests one or more pages starting from a URL — max_pages=1 (the default) ingests just
    that page; a higher value crawls outward to in-scope linked pages (see WebCrawlService)."""
    dto = CrawlRequest.model_validate(request.get_json(silent=True) or {})
    job_id = _service().start_crawl(
        g.org_id,
        g.user_id,
        dto.url,
        dto.max_pages,
        dto.scope_prefix,
        category_id=dto.category_id,
    )
    return jsonify({"job_id": job_id}), 202


@documents_bp.get("/crawl-jobs/<job_id>")
@require_org_session
def get_crawl_job(job_id: str):
    status = _service().get_crawl_job_status(g.org_id, job_id)
    return jsonify(CrawlJobStatusResponse(**status).model_dump())


@documents_bp.get("/documents")
@require_permission("documents:read")
def list_documents():
    query = PaginationQuery.model_validate(request.args.to_dict())
    documents, total = _service().list_documents(
        g.org_id,
        query.limit,
        query.offset,
        query.sort,
        category_id=query.category_id,
        shelf_id=query.shelf_id,
        document_type=query.type,
        title_contains=query.q,
    )
    response = jsonify([DocumentResponse.from_entity(document).model_dump(mode="json") for document in documents])
    response.headers["X-Total-Count"] = str(total)
    return response


@documents_bp.get("/documents/<uuid:document_id>")
@require_permission("documents:read")
def get_document(document_id: UUID):
    document = _service().get_document(g.org_id, document_id)
    retrieval_count, avg_similarity = QueryRepository(get_session()).retrieval_stats_for_document(document_id)
    response = DocumentResponse.from_entity(document, retrieval_count=retrieval_count, avg_similarity=avg_similarity)
    return jsonify(response.model_dump(mode="json"))


@documents_bp.get("/documents/<uuid:document_id>/chunks")
@require_permission("documents:read")
def list_document_chunks(document_id: UUID):
    query = LimitOffsetQuery.model_validate(request.args.to_dict())
    chunks = _service().list_chunks(g.org_id, document_id, query.limit, query.offset)
    return jsonify([ChunkResponse.from_entity(chunk).model_dump(mode="json") for chunk in chunks])


@documents_bp.get("/jobs/<job_id>")
@require_org_session
def get_job(job_id: str):
    status = _service().get_job_status(g.org_id, job_id)
    return jsonify(JobStatusResponse(**status).model_dump())


@documents_bp.post("/jobs/<job_id>/cancel")
@require_org_session
def cancel_job(job_id: str):
    """Best-effort: cancellation is checked between embedding-provider batches, not instant — the
    job's status stays "running" (with cancel_requested now true, see JobStatusResponse) until it
    actually settles on "cancelled"."""
    _service().cancel_job(g.org_id, job_id)
    return "", 202


@documents_bp.delete("/documents/<uuid:document_id>")
@require_permission("documents:write")
def delete_document(document_id: UUID):
    _service().delete_document(g.org_id, document_id)
    return "", 204


@documents_bp.patch("/documents/<uuid:document_id>")
@require_permission("documents:write")
def rename_document(document_id: UUID):
    dto = DocumentRenameRequest.model_validate(request.get_json(silent=True) or {})
    document = _service().rename_document(g.org_id, document_id, dto.title)
    return jsonify(DocumentResponse.from_entity(document).model_dump(mode="json"))


@documents_bp.patch("/documents/<uuid:document_id>/metadata")
@require_permission("documents:write")
def update_document_metadata(document_id: UUID):
    dto = DocumentMetadataUpdateRequest.model_validate(request.get_json(silent=True) or {})
    document = _service().update_metadata(g.org_id, document_id, dto.category_id, dto.type)
    return jsonify(DocumentResponse.from_entity(document).model_dump(mode="json"))


@documents_bp.post("/documents/<uuid:document_id>/retry")
@require_permission("documents:write")
def retry_document(document_id: UUID):
    job_id = _service().start_retry(g.org_id, document_id, g.user_id)
    return jsonify({"job_id": job_id}), 202
