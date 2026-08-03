from typing import Protocol
from uuid import UUID

from datetime import datetime

from app.domain.entities import (
    Application,
    AuthorizationCode,
    Document,
    EmbeddingProviderConfig,
    EmbeddingSettings,
    Library,
    RefreshToken,
    ScoredChunk,
    SearchSettings,
    User,
    WebCrawlSettings,
)

# Protocol (structural typing), not ABC — infra classes satisfy these by shape alone, no
# explicit inheritance needed. Same Dependency Inversion benefit, less ceremony.


class LibraryRepositoryPort(Protocol):
    def create(self, **fields) -> Library: ...

    def get(self, library_id: UUID) -> Library | None: ...

    def update(self, library_id: UUID, name: str, description: str | None) -> Library: ...

    def list(self, limit: int, offset: int, sort: str) -> list[Library]: ...

    def count(self) -> int: ...

    def delete(self, library_id: UUID) -> None: ...

    def increment_counts(self, library_id: UUID, document_delta: int, chunk_delta: int) -> None: ...


class DocumentRepositoryPort(Protocol):
    def create(self, **fields) -> Document: ...

    def get(self, document_id: UUID) -> Document | None: ...

    def list_for_library(self, library_id: UUID, limit: int, offset: int, sort: str) -> list[Document]: ...

    def count_for_library(self, library_id: UUID) -> int: ...

    def update_status(
        self,
        document_id: UUID,
        status: str,
        ingested_at=None,
        error_message: str | None = None,
        chunk_count: int | None = None,
    ) -> Document: ...

    def get_raw_bytes(self, document_id: UUID) -> bytes | None: ...

    def rename(self, document_id: UUID, new_name: str) -> Document: ...

    def delete(self, document_id: UUID) -> None: ...


class ChunkRepositoryPort(Protocol):
    def bulk_create(self, document_id: UUID, library_id: UUID, chunks: list[tuple[int, str, list[float]]]) -> None: ...

    def similarity_search(self, library_id: UUID, query_embedding: list[float], top_k: int) -> list[ScoredChunk]: ...

    def sparse_search(self, library_id: UUID, query_text: str, top_k: int) -> list[ScoredChunk]: ...

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


class WebCrawlSettingsRepositoryPort(Protocol):
    def get(self) -> WebCrawlSettings | None: ...

    def upsert(self, user_agent: str) -> WebCrawlSettings: ...


class UserRepositoryPort(Protocol):
    def get(self) -> User | None: ...

    def create_default(self, username: str, password_hash: str) -> User: ...

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

    def update_secret(self, application_id: UUID, client_secret_hash: str) -> None: ...


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
