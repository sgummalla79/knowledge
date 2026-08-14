from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Library/Document are intentionally thin/anemic (no behavior) — they mirror the persisted
# fields 1:1 and exist only so the application layer depends on plain data, not ORM rows.
# Inventing methods here just to avoid "anemic domain model" would be premature abstraction.


@dataclass(frozen=True)
class Library:
    id: UUID
    name: str
    description: str | None
    document_count: int
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Document:
    id: UUID
    library_id: UUID
    source_filename: str
    file_type: str
    status: str
    error_message: str | None
    size_bytes: int | None
    chunk_count: int | None
    ingested_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ScoredChunk:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    # Higher is always better — whether this is a per-list similarity score or an RRF-fused score
    # depends on which stage of the pipeline produced it. Never a lower-is-better distance, so
    # callers never have to remember which convention applies.
    score: float


@dataclass(frozen=True)
class EmbeddingSettings:
    id: UUID
    provider: str
    model: str
    api_key: str | None
    base_url: str | None
    dimensions: int
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    id: UUID
    provider: str
    enabled: bool
    model: str | None
    api_key: str | None
    base_url: str | None
    dimensions: int | None
    chunk_size: int | None
    chunk_overlap: int | None
    created_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class SearchSettings:
    dense_k: int
    sparse_k: int
    rrf_k: int
    updated_at: datetime | None


@dataclass(frozen=True)
class WebCrawlSettings:
    user_agent: str
    updated_at: datetime | None


@dataclass(frozen=True)
class User:
    id: UUID
    username: str
    password_hash: str
    must_change_password: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Application:
    id: UUID
    name: str
    allowed_scopes: list[str]
    created_at: datetime
    redirect_uris: list[str]


@dataclass(frozen=True)
class RefreshToken:
    id: UUID
    application_id: UUID
    scope: list[str]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True)
class AuthorizationCode:
    id: UUID
    application_id: UUID
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    scope: list[str]
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
