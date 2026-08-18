from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Document is intentionally thin/anemic (no behavior) — it mirrors the persisted fields 1:1 and
# exists only so the application layer depends on plain data, not ORM rows. Inventing methods here
# just to avoid "anemic domain model" would be premature abstraction.


@dataclass(frozen=True)
class Document:
    id: UUID
    org_id: UUID
    source_id: UUID | None
    category_id: UUID | None
    owner_id: UUID
    title: str
    type: str
    # Technical upload format (pdf/md/txt/html) driving parser selection — distinct from `type`
    # above (article/dataset/guide/report/faq/media classification). See the ORM class docstring.
    file_type: str
    content_uri: str | None
    description: str | None
    status: str
    error_message: str | None
    size_bytes: int | None
    chunk_count: int | None
    split_group_id: UUID | None
    split_part: int | None
    split_total: int | None
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime
    indexed_at: datetime | None


@dataclass(frozen=True)
class ScoredChunk:
    id: UUID
    document_id: UUID
    ordinal: int
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
class RoutedScoredChunk:
    category_id: UUID
    category_name: str
    chunk: ScoredChunk


@dataclass(frozen=True)
class Organization:
    id: UUID
    name: str
    slug: str
    plan: str
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class Category:
    id: UUID
    org_id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    description: str | None
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class Tag:
    id: UUID
    org_id: UUID
    name: str
    created_by: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class Query:
    id: UUID
    org_id: UUID
    user_id: UUID | None
    query_text: str
    latency_ms: int | None
    result_count: int | None
    created_at: datetime


@dataclass(frozen=True)
class QueryResult:
    id: int
    query_id: UUID
    chunk_id: UUID
    rank: int
    similarity_score: float


@dataclass(frozen=True)
class Shelf:
    id: UUID
    org_id: UUID
    name: str
    slug: str
    description: str | None
    is_default: bool
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime


@dataclass(frozen=True)
class UserShelfAccess:
    user_id: UUID
    shelf_id: UUID
    granted_by: UUID | None
    granted_at: datetime


@dataclass(frozen=True)
class Source:
    id: UUID
    org_id: UUID
    type: str
    name: str
    config: dict
    api_key_hash: str | None
    status: str
    created_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime
    last_synced_at: datetime | None


@dataclass(frozen=True)
class IngestionJob:
    id: UUID
    org_id: UUID
    source_id: UUID | None
    document_id: UUID | None
    type: str
    status: str
    error_message: str | None
    items_processed: int
    triggered_by: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class Identity:
    """A person, wholly org-independent — see migration 0001's module docstring for why this is
    split from OrgMember below. `email` is globally unique across the whole app, not per-org."""

    id: UUID
    email: str
    name: str
    password_hash: str
    must_change_password: bool
    created_at: datetime
    last_modified_at: datetime
    last_active_at: datetime | None


@dataclass(frozen=True)
class OrgMember:
    """Which orgs an Identity belongs to, and with what role in each — a person can hold a
    different membership (and role) in several orgs and switch between them."""

    id: UUID
    org_id: UUID
    identity_id: UUID
    role: str
    invited_by: UUID | None
    last_modified_by: UUID | None
    created_at: datetime
    last_modified_at: datetime
