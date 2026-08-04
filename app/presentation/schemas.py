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
from app.domain.entities import Document, Library, ScoredChunk, SearchSettings, WebCrawlSettings


class LibraryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class LibraryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None


class PaginationQuery(BaseModel):
    """Shared shape for every paginated list endpoint (libraries, documents, ...)."""

    limit: int = Field(default=100, gt=0, le=500)
    offset: int = Field(default=0, ge=0)
    sort: str = "-created_at"


class LibraryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    document_count: int
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, library: Library) -> "LibraryResponse":
        return cls(
            id=library.id,
            name=library.name,
            description=library.description,
            document_count=library.document_count,
            chunk_count=library.chunk_count,
            last_ingested_at=library.last_ingested_at,
            created_at=library.created_at,
            updated_at=library.updated_at,
        )


class DocumentResponse(BaseModel):
    id: UUID
    library_id: UUID
    source_filename: str
    file_type: str
    status: str
    error_message: str | None
    size_bytes: int | None
    chunk_count: int | None
    split_group_id: UUID | None = None
    split_part: int | None = None
    split_total: int | None = None
    ingested_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            library_id=document.library_id,
            source_filename=document.source_filename,
            file_type=document.file_type,
            status=document.status,
            error_message=document.error_message,
            size_bytes=document.size_bytes,
            chunk_count=document.chunk_count,
            split_group_id=document.split_group_id,
            split_part=document.split_part,
            split_total=document.split_total,
            ingested_at=document.ingested_at,
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

    source_filename: str = Field(min_length=1)


class CrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    max_pages: int = Field(default=1, gt=0, le=WEB_CRAWL_MAX_PAGES_LIMIT)
    scope_prefix: str | None = Field(default=None, min_length=1)


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
    chunk_index: int
    content: str
    score: float

    @classmethod
    def from_entity(cls, chunk: ScoredChunk) -> "ScoredChunkResponse":
        return cls(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=chunk.score,
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


class SearchSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dense_k: int = Field(gt=0, le=100)
    sparse_k: int = Field(gt=0, le=100)
    rrf_k: int = Field(gt=0, le=1000)


class SearchSettingsResponse(BaseModel):
    dense_k: int
    sparse_k: int
    rrf_k: int
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, settings: SearchSettings) -> "SearchSettingsResponse":
        return cls(
            dense_k=settings.dense_k,
            sparse_k=settings.sparse_k,
            rrf_k=settings.rrf_k,
            updated_at=settings.updated_at,
        )


class WebCrawlSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_agent: str = Field(min_length=1)


class WebCrawlSettingsResponse(BaseModel):
    user_agent: str
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, settings: WebCrawlSettings) -> "WebCrawlSettingsResponse":
        return cls(user_agent=settings.user_agent, updated_at=settings.updated_at)


class ScopeGroupResponse(BaseModel):
    """One resource-group bucket of scopes (e.g. "Libraries" -> ["libraries:read",
    "libraries:write"]) — see _grouped_scopes in app/presentation/routes/auth_ui.py."""

    label: str
    scopes: list[str]


class ApplicationResponse(BaseModel):
    id: UUID
    name: str
    allowed_scopes: list[str]
    token_status: str
    last_used_at: datetime | None


class RegisterApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)


class RegisterApplicationResponse(BaseModel):
    id: UUID
    name: str
    allowed_scopes: list[str]
    client_secret: str
