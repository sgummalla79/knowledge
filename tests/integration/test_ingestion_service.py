from unittest.mock import MagicMock, patch

import pytest

from app.application.ingestion_service import IngestionService
from app.constants import EMBEDDING_DIM
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.library_repository import LibraryRepository


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _make_library(library_repo, **overrides):
    fields = dict(name="ingest-test", description=None)
    fields.update(overrides)
    return library_repo.create(**fields)


def _make_service(db_session):
    return IngestionService(
        LibraryRepository(db_session),
        DocumentRepository(db_session),
        ChunkRepository(db_session),
        EmbeddingSettingsRepository(db_session),
    )


def test_successful_ingest_is_atomic(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo)
    EmbeddingSettingsRepository(db_session).upsert("voyage", "voyage-3", "test-key", chunk_size=20, chunk_overlap=5)
    db_session.commit()

    service = _make_service(db_session)
    text = "abcdefghijklmnopqrstuvwxyz" * 3

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(library, "notes.txt", text.encode())
    db_session.commit()

    updated_library = library_repo.get(library.id)
    assert document.status == "completed"
    assert updated_library.document_count == 1
    assert updated_library.chunk_count > 0


def test_failed_embedding_leaves_document_failed_and_counts_unchanged(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-fail-test")
    EmbeddingSettingsRepository(db_session).upsert("voyage", "voyage-3", "test-key", chunk_size=20, chunk_overlap=5)
    db_session.commit()

    service = _make_service(db_session)

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        try:
            service.ingest(library, "notes.txt", b"hello world")
        except RuntimeError:
            pass
    db_session.commit()

    updated_library = library_repo.get(library.id)
    assert updated_library.document_count == 0
    assert updated_library.chunk_count == 0


def test_ingest_without_configured_embeddings_raises(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-unconfigured-test")
    db_session.commit()

    service = _make_service(db_session)

    with pytest.raises(ValidationError) as exc_info:
        service.ingest(library, "notes.txt", b"hello world")
    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED

    # No document row should have been created — the precondition check runs before anything else.
    documents = DocumentRepository(db_session).list_for_library(library.id, limit=10, offset=0, sort="-created_at")
    assert documents == []


def test_embedding_settings_clear_removes_the_row(db_session):
    repo = EmbeddingSettingsRepository(db_session)
    repo.upsert("voyage", "voyage-3", "secret", chunk_size=800, chunk_overlap=100)
    db_session.commit()
    assert repo.get() is not None

    repo.clear()
    db_session.commit()
    assert repo.get() is None
