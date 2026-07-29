import logging
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.document_service import DocumentService, _run_ingestion_job, _run_retry_job
from app.application.ingestion_service import IngestionService
from app.application.job_store import JobStore
from app.constants import EMBEDDING_DIM
from app.domain import error_codes
from app.domain.errors import NotFoundError, ValidationError
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.library_repository import LibraryRepository
from app.logging_config import configure_logging

# _run_ingestion_job calls SessionLocal() internally (app/infrastructure/orm/base.py's module-level
# sessionmaker, bound to config.database_url at import time) — that's the dummy placeholder
# tests/conftest.py sets purely to satisfy Config._require() at import time, not the real
# testcontainers Postgres the db_session/postgres_url fixtures use. Patching
# app.application.document_service.SessionLocal to a sessionmaker bound to postgres_url is the
# same technique already used for app.cli.SessionLocal in test_reembed_migration.py.


@pytest.fixture()
def session_factory(postgres_url):
    engine = create_engine(postgres_url)
    yield sessionmaker(bind=engine)
    engine.dispose()


def test_ingestion_job_failure_logs_exception_with_job_id(db_session, session_factory, caplog):
    # configure_logging is idempotent and safe to call here regardless of whether some earlier
    # test already did — guarantees the ContextFilter that attaches job_id to LogRecords is
    # actually wired up, so this test doesn't depend on suite-wide execution order.
    configure_logging("INFO")

    library = LibraryRepository(db_session).create(name="log-fail-test", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    job_id = JobStore.create()

    with caplog.at_level(logging.INFO):
        with patch("app.application.document_service.SessionLocal", session_factory):
            with patch(
                "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
                side_effect=RuntimeError("embedding API unavailable"),
            ):
                _run_ingestion_job(job_id, library.id, "notes.txt", b"hello world")

    failure_records = [
        record
        for record in caplog.records
        if record.name == "app.application.document_service" and record.levelname == "ERROR"
    ]
    assert len(failure_records) == 1
    assert failure_records[0].job_id == job_id
    assert failure_records[0].exc_info is not None

    status = JobStore.get(job_id)
    assert status["status"] == "failed"


def test_ingestion_job_success_logs_started_and_completed(db_session, session_factory, caplog):
    configure_logging("INFO")

    library = LibraryRepository(db_session).create(name="log-success-test", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    job_id = JobStore.create()
    fake_provider = _fake_provider()

    with caplog.at_level(logging.INFO):
        with patch("app.application.document_service.SessionLocal", session_factory):
            with patch(
                "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
                return_value=fake_provider,
            ):
                _run_ingestion_job(job_id, library.id, "notes.txt", b"hello world")

    job_records = [
        record for record in caplog.records if record.name == "app.application.document_service"
    ]
    messages = [record.getMessage() for record in job_records]
    assert "Ingestion job started" in messages
    assert "Ingestion job completed" in messages
    assert all(record.job_id == job_id for record in job_records)

    status = JobStore.get(job_id)
    assert status["status"] == "completed"


def _fake_provider():
    from unittest.mock import MagicMock

    from app.constants import EMBEDDING_DIM

    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _ingest(library_repo, document_repo, chunk_repo, db_session, library, filename="notes.txt"):
    ingestion_service = IngestionService(
        library_repo, document_repo, chunk_repo, EmbeddingSettingsRepository(db_session)
    )
    text = "abcdefghijklmnopqrstuvwxyz" * 3
    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = ingestion_service.ingest(library, filename, text.encode())
    db_session.commit()
    return document


def test_delete_document_removes_chunks_and_decrements_library_counts(db_session):
    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library = library_repo.create(name="delete-doc-test", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(library_repo, document_repo, chunk_repo, db_session, library)

    ingested_library = library_repo.get(library.id)
    assert ingested_library.document_count == 1
    assert ingested_library.chunk_count > 0

    DocumentService(document_repo, library_repo, chunk_repo).delete_document(library.id, document.id)
    db_session.commit()

    assert document_repo.get(document.id) is None
    assert chunk_repo.count_for_document(document.id) == 0

    final_library = library_repo.get(library.id)
    assert final_library.document_count == 0
    assert final_library.chunk_count == 0


def test_delete_document_from_wrong_library_raises_document_not_found(db_session):
    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library_a = library_repo.create(name="delete-doc-lib-a", description=None)
    library_b = library_repo.create(name="delete-doc-lib-b", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(library_repo, document_repo, chunk_repo, db_session, library_a)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, library_repo, chunk_repo).delete_document(library_b.id, document.id)
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND

    # Nothing should have been touched — still exists, still belongs to library_a.
    assert document_repo.get(document.id) is not None


def test_delete_document_missing_library_raises_library_not_found(db_session):
    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, library_repo, chunk_repo).delete_document(uuid4(), uuid4())
    assert exc_info.value.code == error_codes.LIBRARY_NOT_FOUND


def test_delete_document_missing_document_raises_document_not_found(db_session):
    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library = library_repo.create(name="delete-doc-missing-test", description=None)
    db_session.commit()

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, library_repo, chunk_repo).delete_document(library.id, uuid4())
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND


def _ingest_failing(library_repo, document_repo, chunk_repo, db_session, library, filename="notes.txt"):
    ingestion_service = IngestionService(
        library_repo, document_repo, chunk_repo, EmbeddingSettingsRepository(db_session)
    )
    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            ingestion_service.ingest(library, filename, b"hello world")
    db_session.commit()
    return document_repo.list_for_library(library.id, limit=10, offset=0, sort="-created_at")[0]


def test_start_retry_on_non_failed_document_raises_document_not_retryable(db_session):
    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library = library_repo.create(name="retry-not-failed-test", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(library_repo, document_repo, chunk_repo, db_session, library)  # completed
    assert document.status == "completed"

    with pytest.raises(ValidationError) as exc_info:
        DocumentService(document_repo, library_repo, chunk_repo).start_retry(library.id, document.id)
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_RETRYABLE


def test_start_retry_from_wrong_library_raises_document_not_found(db_session):
    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library_a = library_repo.create(name="retry-lib-a", description=None)
    library_b = library_repo.create(name="retry-lib-b", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    failed_document = _ingest_failing(library_repo, document_repo, chunk_repo, db_session, library_a)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, library_repo, chunk_repo).start_retry(library_b.id, failed_document.id)
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND


def test_retry_job_success_logs_and_completes(db_session, session_factory, caplog):
    configure_logging("INFO")

    library_repo = LibraryRepository(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library = library_repo.create(name="retry-job-success-test", description=None)
    EmbeddingSettingsRepository(db_session).upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    failed_document = _ingest_failing(library_repo, document_repo, chunk_repo, db_session, library)

    job_id = JobStore.create()
    with caplog.at_level(logging.INFO):
        with patch("app.application.document_service.SessionLocal", session_factory):
            with patch(
                "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
                return_value=_fake_provider(),
            ):
                _run_retry_job(job_id, library.id, failed_document.id)

    job_records = [
        record for record in caplog.records if record.name == "app.application.document_service"
    ]
    messages = [record.getMessage() for record in job_records]
    assert "Retry job started" in messages
    assert "Retry job completed" in messages
    assert all(record.job_id == job_id for record in job_records)

    status = JobStore.get(job_id)
    assert status["status"] == "completed"

    final_document = document_repo.get(failed_document.id)
    assert final_document.status == "completed"
    final_library = library_repo.get(library.id)
    assert final_library.document_count == 1
    assert final_library.chunk_count > 0
