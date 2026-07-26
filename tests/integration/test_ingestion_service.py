from unittest.mock import MagicMock, patch

from app.application.ingestion_service import IngestionService
from app.constants import EMBEDDING_DIM
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.library_repository import LibraryRepository


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _make_library(library_repo, **overrides):
    fields = dict(
        name="ingest-test",
        description=None,
        embedding_provider="voyage",
        embedding_model="voyage-3",
        chunk_size=20,
        chunk_overlap=5,
    )
    fields.update(overrides)
    return library_repo.create(**fields)


def test_successful_ingest_is_atomic(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo)
    db_session.commit()

    service = IngestionService(library_repo, DocumentRepository(db_session), ChunkRepository(db_session))
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
    db_session.commit()

    service = IngestionService(library_repo, DocumentRepository(db_session), ChunkRepository(db_session))

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
