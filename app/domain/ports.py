from __future__ import annotations

from typing import Protocol
from uuid import UUID

from datetime import datetime

from app.domain.entities import (
    Application,
    AuthorizationCode,
    Category,
    Document,
    EmbeddingProviderConfig,
    EmbeddingSettings,
    IngestionJob,
    Organization,
    Query,
    QueryResult,
    RefreshToken,
    RouterSettings,
    ScoredChunk,
    SearchSettings,
    Shelf,
    Source,
    Tag,
    User,
    WebCrawlSettings,
)

# Protocol (structural typing), not ABC — infra classes satisfy these by shape alone, no
# explicit inheritance needed. Same Dependency Inversion benefit, less ceremony.


class DocumentRepositoryPort(Protocol):
    def create(self, **fields) -> Document: ...

    def get(self, document_id: UUID) -> Document | None: ...

    def list_for_org(self, org_id: UUID, limit: int, offset: int, sort: str) -> list[Document]: ...

    def count_for_org(self, org_id: UUID) -> int: ...

    def update_status(
        self,
        document_id: UUID,
        status: str,
        indexed_at=None,
        error_message: str | None = None,
        chunk_count: int | None = None,
    ) -> Document: ...

    def get_raw_bytes(self, document_id: UUID) -> bytes | None: ...

    def rename(self, document_id: UUID, new_title: str) -> Document: ...

    def delete(self, document_id: UUID) -> None: ...


class ChunkRepositoryPort(Protocol):
    def bulk_create(
        self,
        document_id: UUID,
        org_id: UUID,
        embedding_model_id: UUID,
        chunks: list[tuple[int, str, int, list[float]]],
    ) -> None: ...

    def similarity_search(self, org_id: UUID, query_embedding: list[float], top_k: int) -> list[ScoredChunk]: ...

    def sparse_search(self, org_id: UUID, query_text: str, top_k: int) -> list[ScoredChunk]: ...

    def count_for_document(self, document_id: UUID) -> int: ...

    def count_all(self) -> int: ...

    def resize_embedding_column(self, dimensions: int) -> None: ...


class EmbeddingSettingsRepositoryPort(Protocol):
    """Read-only view of whichever provider is currently active — the only thing ingestion and
    retrieval ever need. Writes go through EmbeddingProviderSettingsRepositoryPort instead, since
    "active" now means one row among several per-provider configs, not a single global row."""

    def get(self) -> EmbeddingSettings | None: ...


class EmbeddingProviderSettingsRepositoryPort(Protocol):
    def list(self) -> list[EmbeddingProviderConfig]: ...

    def get(self, provider: str) -> EmbeddingProviderConfig | None: ...

    def upsert_config(
        self,
        provider: str,
        model: str,
        api_key: str | None,
        base_url: str | None,
        dimensions: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> EmbeddingProviderConfig: ...

    def set_enabled(self, provider: str, enabled: bool) -> EmbeddingProviderConfig: ...


class SearchSettingsRepositoryPort(Protocol):
    def get(self) -> SearchSettings | None: ...

    def upsert(self, dense_k: int, sparse_k: int, rrf_k: int) -> SearchSettings: ...


class RouterSettingsRepositoryPort(Protocol):
    def get(self) -> RouterSettings | None: ...

    def upsert(self, top_n: int, min_similarity: float) -> RouterSettings: ...


class WebCrawlSettingsRepositoryPort(Protocol):
    def get(self) -> WebCrawlSettings | None: ...

    def upsert(self, user_agent: str) -> WebCrawlSettings: ...


class OrganizationRepositoryPort(Protocol):
    def create(self, name: str, slug: str, **fields) -> Organization: ...

    def get(self, org_id: UUID) -> Organization | None: ...

    def get_by_slug(self, slug: str) -> Organization | None: ...

    def list(self) -> list[Organization]: ...


class CategoryRepositoryPort(Protocol):
    def create(self, org_id: UUID, name: str, slug: str, **fields) -> Category: ...

    def get(self, category_id: UUID) -> Category | None: ...

    def update(self, category_id: UUID, name: str, description: str | None) -> Category: ...

    def list_by_org(self, org_id: UUID) -> list[Category]: ...

    def delete(self, category_id: UUID) -> None: ...

    # Router RAG (routes a category-less query to the most relevant category by cosine
    # similarity) — the direct successor of what LibraryRepositoryPort's equivalent methods did
    # against libraries.description_embedding before categories replaced libraries.
    def set_description_embedding(self, category_id: UUID, embedding: list[float] | None) -> None: ...

    def list_all_with_description(self, org_id: UUID) -> list[Category]: ...

    def clear_all_description_embeddings(self, org_id: UUID) -> None: ...

    def search_by_description_similarity(
        self, org_id: UUID, query_embedding: list[float], top_n: int, min_similarity: float
    ) -> list[tuple[Category, float]]: ...


class TagRepositoryPort(Protocol):
    def create(self, org_id: UUID, name: str, **fields) -> Tag: ...

    def get(self, tag_id: UUID) -> Tag | None: ...

    def list_by_org(self, org_id: UUID) -> list[Tag]: ...

    def tag_document(self, document_id: UUID, tag_id: UUID) -> None: ...

    def untag_document(self, document_id: UUID, tag_id: UUID) -> None: ...

    def list_for_document(self, document_id: UUID) -> list[Tag]: ...


class QueryRepositoryPort(Protocol):
    def create(self, org_id: UUID, query_text: str, **fields) -> Query: ...

    def record_results(self, query_id: UUID, results: list[tuple[UUID, int, float]]) -> None: ...

    def list_by_org(self, org_id: UUID, limit: int, offset: int) -> list[Query]: ...


class ShelfRepositoryPort(Protocol):
    def create(self, org_id: UUID, name: str, slug: str, **fields) -> Shelf: ...

    def get(self, shelf_id: UUID) -> Shelf | None: ...

    def list_by_org(self, org_id: UUID) -> list[Shelf]: ...

    def get_default_for_org(self, org_id: UUID) -> Shelf | None: ...

    def add_document(self, document_id: UUID, shelf_id: UUID) -> None: ...

    def remove_document(self, document_id: UUID, shelf_id: UUID) -> None: ...

    def list_shelves_for_document(self, document_id: UUID) -> list[Shelf]: ...

    def grant_user_access(self, user_id: UUID, shelf_id: UUID, granted_by: UUID | None) -> None: ...

    def revoke_user_access(self, user_id: UUID, shelf_id: UUID) -> None: ...

    def list_accessible_shelf_ids(self, user_id: UUID) -> list[UUID]: ...


class SourceRepositoryPort(Protocol):
    def create(self, org_id: UUID, type: str, name: str, **fields) -> Source: ...

    def get(self, source_id: UUID) -> Source | None: ...

    def list_by_org(self, org_id: UUID) -> list[Source]: ...


class IngestionJobRepositoryPort(Protocol):
    def create(self, org_id: UUID, type: str, **fields) -> IngestionJob: ...

    def get(self, job_id: UUID) -> IngestionJob | None: ...

    def list_by_org(self, org_id: UUID) -> list[IngestionJob]: ...

    def update_status(self, job_id: UUID, status: str, **fields) -> IngestionJob: ...


class UserRepositoryPort(Protocol):
    def get(self) -> User | None: ...

    def get_by_org(self, org_id: UUID) -> list[User]: ...

    def get_by_email(self, org_id: UUID, email: str) -> User | None: ...

    def create_default(self, email: str, password_hash: str, *, org_id: UUID, name: str) -> User: ...

    def update_password(self, user_id: UUID, password_hash: str) -> None: ...


class ApplicationRepositoryPort(Protocol):
    def create(
        self,
        name: str,
        client_secret_hash: str,
        allowed_scopes: list[str],
        redirect_uris: list[str] | None = None,
        id: UUID | None = None,
    ) -> Application: ...

    def list(self) -> list[Application]: ...

    def get(self, application_id: UUID) -> Application | None: ...

    def get_by_name(self, name: str) -> Application | None: ...

    def find_by_credentials(self, application_id: UUID, client_secret_hash: str) -> Application | None: ...

    def update_secret(self, application_id: UUID, client_secret_hash: str) -> None: ...

    def delete(self, application_id: UUID) -> None: ...


class RefreshTokenRepositoryPort(Protocol):
    def create(
        self, application_id: UUID, token_hash: str, scope: list[str], expires_at
    ) -> RefreshToken: ...

    def find_valid_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    def find_current_for_application(self, application_id: UUID) -> RefreshToken | None: ...

    def revoke(self, token_id: UUID) -> None: ...

    def touch_last_used(self, token_id: UUID) -> None: ...


class AuthorizationCodeRepositoryPort(Protocol):
    def create(
        self,
        application_id: UUID,
        code_hash: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: list[str],
        expires_at: datetime,
    ) -> AuthorizationCode: ...

    def find_valid_by_hash(self, code_hash: str) -> AuthorizationCode | None: ...

    def mark_used(self, code_id: UUID) -> None: ...
