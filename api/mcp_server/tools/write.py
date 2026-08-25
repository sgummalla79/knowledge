from uuid import UUID, uuid4

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from api.application.category_service import CategoryService
from api.application.document_service import DocumentService
from api.application.shelf_service import ShelfService
from api.application.tag_service import TagService
from api.config import config
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.infrastructure.repositories.tag_repository import TagRepository
from api.infrastructure.storage.upload_storage import UploadStorage
from api.mcp_server.db import session_scope, set_rls_session_vars
from api.mcp_server.permissions import require_tier_permission

# Mounted at /mcp/write (see mcp_server/server.py) — content-only mutations: documents,
# categories, shelves, tags. Deliberately excludes org members/profiles/applications regardless of
# what a profile would otherwise allow — see the plan this feature followed, same reasoning this
# app's history already used for keeping application registration off the bearer-token API. Each
# tool is a thin wrapper calling the exact same *Service method the matching HTTP route calls — no
# reimplemented logic.

_TIER = "write"


def _document_service(session) -> DocumentService:
    return DocumentService(
        DocumentRepository(session), ChunkRepository(session), IngestionJobRepository(session), CategoryRepository(session)
    )


def _category_service(session) -> CategoryService:
    return CategoryService(CategoryRepository(session), EmbeddingSettingsRepository(session))


def _shelf_service(session) -> ShelfService:
    return ShelfService(ShelfRepository(session))


def _tag_service(session) -> TagService:
    return TagService(TagRepository(session))


def _verify_document_ownership(session, org_id: UUID, document_id: UUID) -> None:
    document = DocumentRepository(session).get(document_id)
    if document is None or document.org_id != org_id:
        raise ToolError("Document not found.")


def register(mcp: FastMCP) -> None:
    # ── Documents ────────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def create_document(title: str, content: str, category_id: str | None = None) -> dict:
        """Ingest a new document from inline markdown/text content (not a file upload — for
        binary files, use the regular REST API). Ingestion is asynchronous, same as the HTTP
        upload endpoint; poll GET /jobs/<job_id> to see when it finishes."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            # Same streaming-to-disk storage the HTTP upload route uses (see
            # api/presentation/routes/documents.py) instead of a bytea payload column -- content
            # here is always small inline text/markdown, so a plain save_bytes() is fine (mirrors
            # IngestionService.ingest_html()'s same reasoning for crawled HTML).
            job_id_arg = uuid4()
            storage = UploadStorage(config.uploads_dir)
            payload_path = storage.path_for_job_upload(caller["org_id"], job_id_arg)
            storage.save_bytes(payload_path, content.encode("utf-8"))
            job_id = _document_service(session).start_ingestion(
                caller["org_id"],
                caller["identity_id"],
                f"{title}.md",
                payload_path,
                job_id=job_id_arg,
                category_id=UUID(category_id) if category_id else None,
            )
            return {"job_id": job_id}

    @mcp.tool()
    def rename_document(document_id: str, title: str) -> dict:
        """Rename an existing document."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            document = _document_service(session).rename_document(caller["org_id"], UUID(document_id), title)
            return {"id": str(document.id), "title": document.title}

    @mcp.tool()
    def update_document_metadata(document_id: str, document_type: str, category_id: str | None = None) -> dict:
        """Update a document's category and/or type ("article" or "document")."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            document = _document_service(session).update_metadata(
                caller["org_id"],
                UUID(document_id),
                UUID(category_id) if category_id else None,
                document_type,
            )
            return {"id": str(document.id), "category_id": str(document.category_id) if document.category_id else None, "type": document.type}

    @mcp.tool()
    def delete_document(document_id: str) -> None:
        """Permanently delete a document and its chunks."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _document_service(session).delete_document(caller["org_id"], UUID(document_id))

    # ── Categories ───────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def create_category(name: str, description: str | None = None, parent_id: str | None = None) -> dict:
        """Create a new category (subject-area grouping)."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "categories:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            category = _category_service(session).create_category(
                caller["org_id"], name, description, UUID(parent_id) if parent_id else None
            )
            return {"id": str(category.id), "name": category.name, "slug": category.slug}

    @mcp.tool()
    def update_category(category_id: str, name: str, description: str | None = None) -> dict:
        """Rename/re-describe an existing category."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "categories:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            category = _category_service(session).update_category(caller["org_id"], UUID(category_id), name, description)
            return {"id": str(category.id), "name": category.name}

    @mcp.tool()
    def delete_category(category_id: str) -> None:
        """Delete a category."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "categories:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _category_service(session).delete_category(caller["org_id"], UUID(category_id))

    # ── Shelves ──────────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def create_shelf(name: str, description: str | None = None) -> dict:
        """Create a new shelf (access-control grouping)."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "shelves:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            shelf = _shelf_service(session).create_shelf(caller["org_id"], name, description)
            return {"id": str(shelf.id), "name": shelf.name, "slug": shelf.slug}

    @mcp.tool()
    def update_shelf(shelf_id: str, name: str, description: str | None = None) -> dict:
        """Rename/re-describe an existing shelf."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "shelves:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            shelf = _shelf_service(session).update_shelf(caller["org_id"], UUID(shelf_id), name, description)
            return {"id": str(shelf.id), "name": shelf.name}

    @mcp.tool()
    def delete_shelf(shelf_id: str) -> None:
        """Delete a shelf."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "shelves:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _shelf_service(session).delete_shelf(caller["org_id"], UUID(shelf_id))

    @mcp.tool()
    def add_document_to_shelf(shelf_id: str, document_id: str) -> None:
        """Add a document to a shelf."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "shelves:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _verify_document_ownership(session, caller["org_id"], UUID(document_id))
            _shelf_service(session).add_document(caller["org_id"], UUID(shelf_id), UUID(document_id))

    @mcp.tool()
    def remove_document_from_shelf(shelf_id: str, document_id: str) -> None:
        """Remove a document from a shelf."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "shelves:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _verify_document_ownership(session, caller["org_id"], UUID(document_id))
            _shelf_service(session).remove_document(caller["org_id"], UUID(shelf_id), UUID(document_id))

    # ── Tags ─────────────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    def create_tag(name: str) -> dict:
        """Create a new tag."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "tags:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            tag = _tag_service(session).create_tag(caller["org_id"], name)
            return {"id": str(tag.id), "name": tag.name}

    @mcp.tool()
    def tag_document(document_id: str, tag_id: str) -> None:
        """Apply an existing tag to a document."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "tags:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _verify_document_ownership(session, caller["org_id"], UUID(document_id))
            _tag_service(session).tag_document(caller["org_id"], UUID(document_id), UUID(tag_id))

    @mcp.tool()
    def untag_document(document_id: str, tag_id: str) -> None:
        """Remove a tag from a document."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "tags:write")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _verify_document_ownership(session, caller["org_id"], UUID(document_id))
            _tag_service(session).untag_document(caller["org_id"], UUID(document_id), UUID(tag_id))
