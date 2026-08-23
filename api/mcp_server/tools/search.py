import time
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from api.application.category_router_service import CategoryRouterService
from api.application.query_history_service import QueryHistoryService
from api.application.retrieval_service import RetrievalService
from api.constants import DEFAULT_TOP_K
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.mcp_server.db import session_scope, set_rls_session_vars
from api.mcp_server.permissions import require_tier_permission

# Mounted at /mcp/search (see mcp_server/server.py) — everything an LLM client needs to search
# this org's knowledge base and read what it found, nothing else. Moved from the original flat
# tools.py, not rewritten.

_TIER = "search"


def _document_dict(document) -> dict:
    return {
        "id": str(document.id),
        "title": document.title,
        "type": document.type,
        "status": document.status,
        "category_id": str(document.category_id) if document.category_id else None,
        "description": document.description,
        "created_at": document.created_at.isoformat(),
    }


def _get_org_document(session, org_id: UUID, document_id: str):
    document = DocumentRepository(session).get(UUID(document_id))
    if document is None or document.org_id != org_id:
        raise ToolError("Document not found.")
    return document


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def search(query: str, top_k: int = DEFAULT_TOP_K, category_id: str | None = None) -> dict:
        """Hybrid (dense+sparse) search across the connected org's knowledge base. Omit
        category_id to search every category at once, automatically ranked and merged; pass one
        (from list_categories) to search within just that category."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "queries:execute")
            org_id = caller["org_id"]
            set_rls_session_vars(session, org_id, caller["identity_id"])
            retrieval = RetrievalService(ChunkRepository(session), EmbeddingSettingsRepository(session))
            history = QueryHistoryService(QueryRepository(session))
            start = time.monotonic()

            if category_id:
                chunks = retrieval.query(org_id, query, top_k, category_id=UUID(category_id))
                latency_ms = int((time.monotonic() - start) * 1000)
                history.record(org_id, caller["identity_id"], query, latency_ms, chunks)
                documents = {
                    document.id: document
                    for document in DocumentRepository(session).list_by_ids(
                        list({chunk.document_id for chunk in chunks})
                    )
                }
                return {
                    "chunks": [
                        {
                            "id": str(chunk.id),
                            "document_id": str(chunk.document_id),
                            "ordinal": chunk.ordinal,
                            "content": chunk.content,
                            "score": chunk.score,
                            "document_title": documents[chunk.document_id].title
                            if chunk.document_id in documents
                            else "",
                        }
                        for chunk in chunks
                    ]
                }

            router = CategoryRouterService(CategoryRepository(session), EmbeddingSettingsRepository(session), retrieval)
            results = router.query(org_id, query, top_k)
            latency_ms = int((time.monotonic() - start) * 1000)
            history.record(org_id, caller["identity_id"], query, latency_ms, [result.chunk for result in results])
            documents = {
                document.id: document
                for document in DocumentRepository(session).list_by_ids(
                    list({result.chunk.document_id for result in results})
                )
            }
            return {
                "chunks": [
                    {
                        "id": str(result.chunk.id),
                        "document_id": str(result.chunk.document_id),
                        "ordinal": result.chunk.ordinal,
                        "content": result.chunk.content,
                        "score": result.chunk.score,
                        "category_id": str(result.category_id),
                        "category_name": result.category_name,
                        "document_title": documents[result.chunk.document_id].title
                        if result.chunk.document_id in documents
                        else "",
                        "document_type": documents[result.chunk.document_id].type
                        if result.chunk.document_id in documents
                        else "",
                    }
                    for result in results
                ]
            }

    @mcp.tool()
    def list_categories() -> list[dict]:
        """List every category (subject-area grouping) in the connected org."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "categories:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            categories = CategoryRepository(session).list_by_org(caller["org_id"])
            return [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "slug": category.slug,
                    "description": category.description,
                    "parent_id": str(category.parent_id) if category.parent_id else None,
                }
                for category in categories
            ]

    @mcp.tool()
    def get_document(document_id: str) -> dict:
        """Fetch one document's metadata by id."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            document = _get_org_document(session, caller["org_id"], document_id)
            return _document_dict(document)

    @mcp.tool()
    def get_document_chunks(document_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
        """Fetch a document's persisted chunks by id — use after search or get_document to read a
        promising document's full indexed content."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            _get_org_document(session, caller["org_id"], document_id)
            chunks = ChunkRepository(session).list_for_document(UUID(document_id), limit, offset)
            return [
                {"id": str(chunk.id), "ordinal": chunk.ordinal, "content": chunk.content, "token_count": chunk.token_count}
                for chunk in chunks
            ]
