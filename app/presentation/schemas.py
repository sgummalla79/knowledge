from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.constants import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_TOP_K,
)
from app.domain.entities import Document, Library, ScoredChunk


class LibraryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, gt=0)
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, ge=0)


class PaginationQuery(BaseModel):
    """Shared shape for every paginated list endpoint (libraries, documents, ...)."""

    limit: int = Field(default=100, gt=0, le=500)
    offset: int = Field(default=0, ge=0)
    sort: str = "-created_at"


class LibraryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    embedding_provider: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
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
            embedding_provider=library.embedding_provider,
            embedding_model=library.embedding_model,
            chunk_size=library.chunk_size,
            chunk_overlap=library.chunk_overlap,
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
            ingested_at=document.ingested_at,
            created_at=document.created_at,
        )


class JobStatusResponse(BaseModel):
    status: str
    error: str | None
    document_id: str | None


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, gt=0, le=100)


class ScoredChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    distance: float

    @classmethod
    def from_entity(cls, chunk: ScoredChunk) -> "ScoredChunkResponse":
        return cls(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            distance=chunk.distance,
        )
