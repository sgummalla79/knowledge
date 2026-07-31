from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_TOP_K,
    WEB_CRAWL_MAX_PAGES_LIMIT,
)
from app.application.embedding_settings_service import EmbeddingSettingsStatus
from app.domain.entities import Document, EmbeddingProviderToggle, Library, ScoredChunk, SearchSettings


class LibraryCreateRequest(BaseModel):
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
            ingested_at=document.ingested_at,
            created_at=document.created_at,
        )


class JobStatusResponse(BaseModel):
    status: str
    error: str | None
    document_id: str | None
    cancel_requested: bool = False


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


class EmbeddingSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, min_length=1)
    dimensions: int = Field(gt=0)
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, gt=0)
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, ge=0)


class EmbeddingSettingsResponse(BaseModel):
    provider: str | None
    model: str | None
    configured: bool
    base_url: str | None
    dimensions: int | None
    chunk_size: int
    chunk_overlap: int
    updated_at: datetime | None

    @classmethod
    def from_status(cls, status: EmbeddingSettingsStatus) -> "EmbeddingSettingsResponse":
        return cls(
            provider=status.provider,
            model=status.model,
            configured=status.configured,
            base_url=status.base_url,
            dimensions=status.dimensions,
            chunk_size=status.chunk_size,
            chunk_overlap=status.chunk_overlap,
            updated_at=status.updated_at,
        )


class EmbeddingProviderToggleResponse(BaseModel):
    provider: str
    enabled: bool
    updated_at: datetime

    @classmethod
    def from_entity(cls, toggle: EmbeddingProviderToggle) -> "EmbeddingProviderToggleResponse":
        return cls(provider=toggle.provider, enabled=toggle.enabled, updated_at=toggle.updated_at)


class EmbeddingProviderToggleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SearchSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rerank_enabled: bool
    rerank_provider: str = Field(min_length=1)
    rerank_model: str = Field(min_length=1)
    dense_k: int = Field(gt=0, le=100)
    sparse_k: int = Field(gt=0, le=100)
    rerank_candidates: int = Field(gt=0, le=100)
    rrf_k: int = Field(gt=0, le=1000)


class SearchSettingsResponse(BaseModel):
    rerank_enabled: bool
    rerank_provider: str
    rerank_model: str
    dense_k: int
    sparse_k: int
    rerank_candidates: int
    rrf_k: int
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, settings: SearchSettings) -> "SearchSettingsResponse":
        return cls(
            rerank_enabled=settings.rerank_enabled,
            rerank_provider=settings.rerank_provider,
            rerank_model=settings.rerank_model,
            dense_k=settings.dense_k,
            sparse_k=settings.sparse_k,
            rerank_candidates=settings.rerank_candidates,
            rrf_k=settings.rrf_k,
            updated_at=settings.updated_at,
        )
