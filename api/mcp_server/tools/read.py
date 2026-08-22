from uuid import UUID

from mcp.server.fastmcp import FastMCP

from api.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.infrastructure.repositories.tag_repository import TagRepository
from api.mcp_server.db import session_scope, set_rls_session_vars
from api.mcp_server.permissions import require_tier_permission

# Mounted at /mcp/read (see mcp_server/server.py) — object visibility beyond RAG search: shelves,
# documents-by-listing, tags, and embedding model config status. Deliberately excludes org member/
# profile/application visibility (admin-surface, a later "admin capabilities" pass — see the plan
# this feature followed).

_TIER = "read"


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


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_shelves() -> list[dict]:
        """List every shelf (access-control grouping) in the connected org."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "shelves:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            shelves = ShelfRepository(session).list_by_org(caller["org_id"])
            return [
                {"id": str(shelf.id), "name": shelf.name, "slug": shelf.slug, "description": shelf.description}
                for shelf in shelves
            ]

    @mcp.tool()
    def list_documents(
        category_id: str | None = None, shelf_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """List documents in the connected org, optionally filtered by category or shelf id."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "documents:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            documents = DocumentRepository(session).list_for_org(
                caller["org_id"],
                limit,
                offset,
                "-created_at",
                category_id=UUID(category_id) if category_id else None,
                shelf_id=UUID(shelf_id) if shelf_id else None,
            )
            return [_document_dict(document) for document in documents]

    @mcp.tool()
    def list_tags() -> list[dict]:
        """List every tag in the connected org."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "tags:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            tags = TagRepository(session).list_by_org(caller["org_id"])
            return [{"id": str(tag.id), "name": tag.name} for tag in tags]

    @mcp.tool()
    def list_embedding_models() -> list[dict]:
        """List the connected org's known embedding providers and each one's configuration
        status (configured/enabled/locked, model, dimensions) — never includes the raw API key."""
        with session_scope() as session:
            caller = require_tier_permission(session, _TIER, "embedding_models:read")
            set_rls_session_vars(session, caller["org_id"], caller["identity_id"])
            service = EmbeddingProviderConfigService(
                EmbeddingProviderSettingsRepository(session), ChunkRepository(session), CategoryRepository(session)
            )
            statuses = service.list_status(caller["org_id"])
            return [
                {
                    "provider": status.provider,
                    "enabled": status.enabled,
                    "configured": status.configured,
                    "locked": status.locked,
                    "model": status.model,
                    "dimensions": status.dimensions,
                    "active_provider": status.active_provider,
                }
                for status in statuses
            ]
