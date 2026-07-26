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
    embedding_provider: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
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
    ingested_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ScoredChunk:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    distance: float
