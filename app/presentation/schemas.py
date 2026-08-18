from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_TOP_K,
    WEB_CRAWL_MAX_PAGES_LIMIT,
)
from app.application.embedding_provider_settings_service import EmbeddingProviderConfigStatus
from app.domain.entities import Category, Document, RoutedScoredChunk, ScoredChunk


class CategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    parent_id: UUID | None = None


class CategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class PaginationQuery(BaseModel):
    """Shared shape for every paginated list endpoint (documents, ...)."""

    limit: int = Field(default=100, gt=0, le=500)
    offset: int = Field(default=0, ge=0)
    sort: str = "-created_at"


class CategoryResponse(BaseModel):
    id: UUID
    org_id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    description: str | None
    created_at: datetime
    last_modified_at: datetime

    @classmethod
    def from_entity(cls, category: Category) -> "CategoryResponse":
        return cls(
            id=category.id,
            org_id=category.org_id,
            parent_id=category.parent_id,
            name=category.name,
            slug=category.slug,
            description=category.description,
            created_at=category.created_at,
            last_modified_at=category.last_modified_at,
        )


class DocumentResponse(BaseModel):
    id: UUID
    org_id: UUID
    title: str
    file_type: str
    status: str
    error_message: str | None
    size_bytes: int | None
    chunk_count: int | None
    split_group_id: UUID | None = None
    split_part: int | None = None
    split_total: int | None = None
    indexed_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            org_id=document.org_id,
            title=document.title,
            file_type=document.file_type,
            status=document.status,
            error_message=document.error_message,
            size_bytes=document.size_bytes,
            chunk_count=document.chunk_count,
            split_group_id=document.split_group_id,
            split_part=document.split_part,
            split_total=document.split_total,
            indexed_at=document.indexed_at,
            created_at=document.created_at,
        )


class JobStatusResponse(BaseModel):
    status: str
    error: str | None
    document_id: str | None
    cancel_requested: bool = False
    # Populated only for an ingestion that split an oversized PDF into multiple parts
    # (PdfSplitIngestionService) — parts_total == 1 (the default single-document case) means
    # document_id above is the whole story; parts_total > 1 means document_ids lists every
    # successfully-ingested part and parts_failed may be > 0 even though the job itself completed.
    document_ids: list[str] = []
    parts_total: int | None = None
    parts_completed: int = 0
    parts_failed: int = 0


class DocumentRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    max_pages: int = Field(default=1, gt=0, le=WEB_CRAWL_MAX_PAGES_LIMIT)
    scope_prefix: str | None = Field(default=None, min_length=1)
    category_id: UUID | None = None


class CrawlPageStatus(BaseModel):
    status: str
    document_id: str | None
    error: str | None


class CrawlJobStatusResponse(BaseModel):
    status: str
    seed_url: str
    error: str | None
    pages: dict[str, CrawlPageStatus]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, gt=0, le=100)


class ScoredChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    score: float

    @classmethod
    def from_entity(cls, chunk: ScoredChunk) -> "ScoredChunkResponse":
        return cls(
            id=chunk.id,
            document_id=chunk.document_id,
            ordinal=chunk.ordinal,
            content=chunk.content,
            score=chunk.score,
        )


class RoutedScoredChunkResponse(BaseModel):
    category_id: UUID
    category_name: str
    id: UUID
    document_id: UUID
    ordinal: int
    content: str
    score: float

    @classmethod
    def from_entity(cls, routed: RoutedScoredChunk) -> "RoutedScoredChunkResponse":
        return cls(
            category_id=routed.category_id,
            category_name=routed.category_name,
            id=routed.chunk.id,
            document_id=routed.chunk.document_id,
            ordinal=routed.chunk.ordinal,
            content=routed.chunk.content,
            score=routed.chunk.score,
        )


class EmbeddingModelListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)


class EmbeddingProviderConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    dimensions: int = Field(gt=0)
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, gt=0)
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, ge=0)


class EmbeddingProviderConfigResponse(BaseModel):
    provider: str
    enabled: bool
    configured: bool
    locked: bool
    locked_by_other: bool
    chunk_count: int
    model: str | None
    base_url: str | None
    dimensions: int | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None
    active_provider: str | None

    @classmethod
    def from_status(cls, status: EmbeddingProviderConfigStatus) -> "EmbeddingProviderConfigResponse":
        return cls(
            provider=status.provider,
            enabled=status.enabled,
            configured=status.configured,
            locked=status.locked,
            locked_by_other=status.locked_by_other,
            chunk_count=status.chunk_count,
            model=status.model,
            base_url=status.base_url,
            dimensions=status.dimensions,
            chunk_size=status.chunk_size,
            chunk_overlap=status.chunk_overlap,
            updated_at=status.updated_at,
            active_provider=status.active_provider,
        )


