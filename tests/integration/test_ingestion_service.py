from unittest.mock import MagicMock, patch

import pytest

from app.application.ingestion_service import IngestionService
from app.constants import EMBEDDING_DIM
from app.domain import error_codes
from app.domain.errors import IngestionCancelled, ValidationError
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.library_repository import LibraryRepository
from tests.integration.conftest import seed_active_embedding_provider


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
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
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
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
    assert document.size_bytes == len(text.encode())
    assert document.chunk_count > 0
    assert document.chunk_count == updated_library.chunk_count
    assert updated_library.document_count == 1
    assert updated_library.chunk_count > 0


def test_ingest_strips_nul_bytes_from_extracted_text_instead_of_failing(db_session):
    """Regression test for a real incident: a PDF's extracted text contained a NUL byte, which
    Postgres rejects outright when inserting into chunks.content ("A string literal cannot
    contain NUL (0x00) characters") -- and that DB-level failure cascaded into the document never
    being markable "failed" either (see test_chunk_repository.py). Stripping NUL bytes right after
    parsing means this content class no longer reaches the DB at all.
    """
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-nul-byte-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    text_with_nul = "some real content \x00 with an embedded null byte " * 3

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(library, "notes.txt", text_with_nul.encode())
    db_session.commit()

    assert document.status == "completed"
    assert document.chunk_count > 0


def test_ingest_with_dimension_mismatch_fails_document_and_leaves_counts_unchanged(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-dimension-mismatch-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    wrong_dimension_provider = MagicMock()
    wrong_dimension_provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * (EMBEDDING_DIM // 2) for _ in texts]

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=wrong_dimension_provider,
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.ingest(library, "notes.txt", b"hello world")
    db_session.commit()
    assert exc_info.value.code == error_codes.EMBEDDING_DIMENSION_MISMATCH

    updated_library = library_repo.get(library.id)
    assert updated_library.document_count == 0
    assert updated_library.chunk_count == 0


def test_failed_embedding_leaves_document_failed_and_counts_unchanged(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-fail-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
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


def test_successful_ingest_clears_raw_bytes_after_completion(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-clears-bytes-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)
    text = "abcdefghijklmnopqrstuvwxyz" * 3

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(library, "notes.txt", text.encode())
    db_session.commit()

    # The original file is only needed to retry a failed ingestion — once completed, it's dead
    # weight and should be reclaimed automatically (DocumentRepository.update_status).
    assert document_repo.get_raw_bytes(document.id) is None
    assert document.error_message is None


def test_failed_ingest_keeps_raw_bytes_and_records_error_message(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-keeps-bytes-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest(library, "notes.txt", b"hello world")
    db_session.commit()

    documents = document_repo.list_for_library(library.id, limit=10, offset=0, sort="-created_at")
    assert len(documents) == 1
    failed_document = documents[0]
    assert failed_document.status == "failed"
    assert "embedding API unavailable" in failed_document.error_message
    assert document_repo.get_raw_bytes(failed_document.id) == b"hello world"
    # size_bytes is set at upload time regardless of outcome; chunk_count stays unset ("not
    # available yet") since ingestion never reached completion.
    assert failed_document.size_bytes == len(b"hello world")
    assert failed_document.chunk_count is None


def test_retry_after_failure_succeeds_without_double_counting(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="retry-success-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)
    text = "abcdefghijklmnopqrstuvwxyz" * 3

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest(library, "notes.txt", text.encode())
    db_session.commit()

    failed_document = document_repo.list_for_library(library.id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"
    after_failure_library = library_repo.get(library.id)
    assert after_failure_library.document_count == 0
    assert after_failure_library.chunk_count == 0

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(failed_document, library)
    db_session.commit()

    assert retried_document.status == "completed"
    assert retried_document.error_message is None
    assert retried_document.chunk_count > 0
    assert document_repo.get_raw_bytes(retried_document.id) is None

    final_library = library_repo.get(library.id)
    assert final_library.document_count == 1
    assert final_library.chunk_count > 0


def test_retry_without_stored_bytes_raises_document_not_retryable(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="retry-no-bytes-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    # Simulates a document that predates raw-bytes storage (or whose bytes were already cleared) —
    # created directly via the repository, bypassing IngestionService.ingest(), so raw_file_bytes
    # stays NULL.
    document_repo = DocumentRepository(db_session)
    document = document_repo.create(
        library_id=library.id,
        source_filename="legacy.txt",
        file_type="txt",
        content_hash="deadbeef",
        status="failed",
    )
    db_session.commit()

    service = _make_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.retry(document, library)
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_RETRYABLE


def test_retry_without_configured_embeddings_raises(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="retry-unconfigured-test")
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    document = document_repo.create(
        library_id=library.id,
        source_filename="notes.txt",
        file_type="txt",
        content_hash="deadbeef",
        status="failed",
        raw_file_bytes=b"hello world",
    )
    db_session.commit()

    service = _make_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.retry(document, library)
    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED


def test_ingest_html_creates_html_typed_document_and_completes(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-html-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    html = b"<html><body><p>" + b"hello world " * 20 + b"</p></body></html>"

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest_html(library, "https://example.com/docs/page.htm", html)
    db_session.commit()

    assert document.status == "completed"
    assert document.file_type == "html"
    assert document.source_filename == "https://example.com/docs/page.htm"
    assert document.size_bytes == len(html)
    assert document.chunk_count > 0

    updated_library = library_repo.get(library.id)
    assert updated_library.document_count == 1
    assert updated_library.chunk_count == document.chunk_count


def test_retry_of_a_failed_crawled_page_uses_the_html_parser(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="retry-crawled-page-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)
    html = b"<html><body><p>" + b"hello world " * 20 + b"</p></body></html>"

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest_html(library, "https://example.com/docs/page.htm", html)
    db_session.commit()

    failed_document = document_repo.list_for_library(library.id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"
    assert failed_document.file_type == "html"

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(failed_document, library)
    db_session.commit()

    assert retried_document.status == "completed"
    assert retried_document.chunk_count > 0


def test_rename_does_not_break_retry_parser_resolution(db_session):
    """Regression test: parser selection on retry used to re-derive the extension from
    source_filename on every call, so renaming a document to something without a matching
    extension would silently break retry. _resolve_parser now keys off the stored, immutable
    file_type column instead (see ParserRegistry.resolve_by_file_type), so a rename is safe.
    """
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="rename-retry-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest(library, "notes.txt", b"hello world")
    db_session.commit()

    failed_document = document_repo.list_for_library(library.id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"
    assert failed_document.file_type == "txt"

    # Renamed to something with no matching extension at all — parser resolution must still work
    # on retry, since it now keys off file_type ("txt"), not this new name.
    renamed = document_repo.rename(failed_document.id, "completely-different-name")
    assert renamed.source_filename == "completely-different-name"
    db_session.commit()

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(renamed, library)
    db_session.commit()

    assert retried_document.status == "completed"
    assert retried_document.chunk_count > 0


def test_ingest_cancelled_immediately_marks_document_cancelled_not_failed(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="ingest-cancel-test")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)

    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        with pytest.raises(IngestionCancelled):
            service.ingest(library, "notes.txt", b"hello world", should_cancel=lambda: True)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    cancelled_document = document_repo.list_for_library(library.id, limit=10, offset=0, sort="-created_at")[0]
    assert cancelled_document.status == "cancelled"

    updated_library = library_repo.get(library.id)
    assert updated_library.document_count == 0
    assert updated_library.chunk_count == 0


def test_embedding_settings_repository_reflects_whichever_provider_is_enabled(db_session):
    repo = EmbeddingSettingsRepository(db_session)
    assert repo.get() is None

    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "secret", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()
    assert repo.get().provider == "voyage"

    from app.infrastructure.repositories.embedding_provider_settings_repository import (
        EmbeddingProviderSettingsRepository,
    )

    EmbeddingProviderSettingsRepository(db_session).set_enabled("voyage", False)
    db_session.commit()
    assert repo.get() is None
