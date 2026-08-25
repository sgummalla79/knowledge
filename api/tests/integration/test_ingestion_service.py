from unittest.mock import MagicMock, patch

import pytest

from api.application.ingestion_service import IngestionService
from api.constants import EMBEDDING_DIM, INGESTION_EMBED_BATCH_SIZE
from api.domain import error_codes
from api.domain.errors import IngestionCancelled, ValidationError
from api.infrastructure.auth.bootstrap import bootstrap_default_identity, bootstrap_default_organization
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.tests.integration.conftest import seed_active_embedding_provider


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _make_service(db_session):
    return IngestionService(
        DocumentRepository(db_session),
        ChunkRepository(db_session),
        EmbeddingSettingsRepository(db_session),
    )


def _owner(db_session):
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get()


def test_successful_ingest_is_atomic(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    text = "abcdefghijklmnopqrstuvwxyz" * 3

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(org_id, owner.id, "notes.txt", text.encode())
    db_session.commit()

    assert document.status == "indexed"
    assert document.size_bytes == len(text.encode())
    assert document.chunk_count > 0
    assert ChunkRepository(db_session).count_for_document(document.id) == document.chunk_count
    assert document.type == "document"


def test_ingest_html_defaults_to_article_type(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    html = b"<html><body><p>" + b"hello world " * 20 + b"</p></body></html>"

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest_html(org_id, owner.id, "https://example.com/docs", html)
    db_session.commit()

    assert document.type == "article"


def test_ingest_strips_nul_bytes_from_extracted_text_instead_of_failing(db_session):
    """Regression test for a real incident: a PDF's extracted text contained a NUL byte, which
    Postgres rejects outright when inserting into chunks.content ("A string literal cannot
    contain NUL (0x00) characters") -- and that DB-level failure cascaded into the document never
    being markable "failed" either (see test_chunk_repository.py). Stripping NUL bytes right after
    parsing means this content class no longer reaches the DB at all.
    """
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    text_with_nul = "some real content \x00 with an embedded null byte " * 3

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(org_id, owner.id, "notes.txt", text_with_nul.encode())
    db_session.commit()

    assert document.status == "indexed"
    assert document.chunk_count > 0


def test_ingest_with_dimension_mismatch_fails_document_and_creates_no_chunks(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    wrong_dimension_provider = MagicMock()
    wrong_dimension_provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * (EMBEDDING_DIM // 2) for _ in texts]

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=wrong_dimension_provider,
    ):
        with pytest.raises(ValidationError) as exc_info:
            service.ingest(org_id, owner.id, "notes.txt", b"hello world")
    db_session.commit()
    assert exc_info.value.code == error_codes.EMBEDDING_DIMENSION_MISMATCH

    documents = DocumentRepository(db_session).list_for_org(org_id, limit=10, offset=0, sort="-created_at")
    assert len(documents) == 1
    assert documents[0].status == "failed"
    assert ChunkRepository(db_session).count_for_document(documents[0].id) == 0


def test_failed_embedding_leaves_document_failed_and_creates_no_chunks(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        try:
            service.ingest(org_id, owner.id, "notes.txt", b"hello world")
        except RuntimeError:
            pass
    db_session.commit()

    documents = DocumentRepository(db_session).list_for_org(org_id, limit=10, offset=0, sort="-created_at")
    assert len(documents) == 1
    assert documents[0].status == "failed"
    assert ChunkRepository(db_session).count_for_document(documents[0].id) == 0


def test_ingest_without_configured_embeddings_raises(db_session):
    owner = _owner(db_session)
    org = bootstrap_default_organization(db_session)
    db_session.commit()

    service = _make_service(db_session)

    with pytest.raises(ValidationError) as exc_info:
        service.ingest(org.id, owner.id, "notes.txt", b"hello world")
    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED

    # No document row should have been created — the precondition check runs before anything else.
    documents = DocumentRepository(db_session).list_for_org(org.id, limit=10, offset=0, sort="-created_at")
    assert documents == []


def test_successful_ingest_clears_raw_bytes_after_completion(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)
    text = "abcdefghijklmnopqrstuvwxyz" * 3

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(org_id, owner.id, "notes.txt", text.encode())
    db_session.commit()

    # The original file is only needed to retry a failed ingestion — once indexed, it's dead
    # weight and should be reclaimed automatically (DocumentRepository.update_status).
    assert document_repo.get_raw_bytes(document.id) is None
    assert document.error_message is None


def test_failed_ingest_keeps_raw_bytes_and_records_error_message(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest(org_id, owner.id, "notes.txt", b"hello world")
    db_session.commit()

    documents = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")
    assert len(documents) == 1
    failed_document = documents[0]
    assert failed_document.status == "failed"
    assert "embedding API unavailable" in failed_document.error_message
    assert document_repo.get_raw_bytes(failed_document.id) == b"hello world"
    # size_bytes is set at upload time regardless of outcome; chunk_count stays unset ("not
    # available yet") since ingestion never reached indexed.
    assert failed_document.size_bytes == len(b"hello world")
    assert failed_document.chunk_count is None


def test_retry_after_failure_succeeds(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)
    text = "abcdefghijklmnopqrstuvwxyz" * 3

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest(org_id, owner.id, "notes.txt", text.encode())
    db_session.commit()

    failed_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(failed_document)
    db_session.commit()

    assert retried_document.status == "indexed"
    assert retried_document.error_message is None
    assert retried_document.chunk_count > 0
    assert document_repo.get_raw_bytes(retried_document.id) is None


def test_retry_without_stored_bytes_raises_document_not_retryable(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    # Simulates a document that predates raw-bytes storage (or whose bytes were already cleared) —
    # created directly via the repository, bypassing IngestionService.ingest(), so raw_file_bytes
    # stays NULL.
    document_repo = DocumentRepository(db_session)
    document = document_repo.create(
        org_id=org_id,
        owner_id=owner.id,
        title="legacy.txt",
        type="article",
        file_type="txt",
        content_hash="deadbeef",
        status="failed",
    )
    db_session.commit()

    service = _make_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.retry(document)
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_RETRYABLE


def test_retry_without_configured_embeddings_raises(db_session):
    owner = _owner(db_session)
    org = bootstrap_default_organization(db_session)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    document = document_repo.create(
        org_id=org.id,
        owner_id=owner.id,
        title="notes.txt",
        type="article",
        file_type="txt",
        content_hash="deadbeef",
        status="failed",
        raw_file_bytes=b"hello world",
    )
    db_session.commit()

    service = _make_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.retry(document)
    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED


def test_ingest_html_creates_html_typed_document_and_completes(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)
    html = b"<html><body><p>" + b"hello world " * 20 + b"</p></body></html>"

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest_html(org_id, owner.id, "https://example.com/docs/page.htm", html)
    db_session.commit()

    assert document.status == "indexed"
    assert document.file_type == "html"
    assert document.title == "https://example.com/docs/page.htm"
    assert document.size_bytes == len(html)
    assert document.chunk_count > 0


def test_retry_of_a_failed_crawled_page_uses_the_html_parser(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)
    html = b"<html><body><p>" + b"hello world " * 20 + b"</p></body></html>"

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest_html(org_id, owner.id, "https://example.com/docs/page.htm", html)
    db_session.commit()

    failed_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"
    assert failed_document.file_type == "html"

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(failed_document)
    db_session.commit()

    assert retried_document.status == "indexed"
    assert retried_document.chunk_count > 0


def test_rename_does_not_break_retry_parser_resolution(db_session):
    """Regression test: parser selection on retry used to re-derive the extension from the
    display title on every call, so renaming a document to something without a matching extension
    would silently break retry. _resolve_parser now keys off the stored, immutable file_type
    column instead (see ParserRegistry.resolve_by_file_type), so a rename is safe.
    """
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    service = _make_service(db_session)

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            service.ingest(org_id, owner.id, "notes.txt", b"hello world")
    db_session.commit()

    failed_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"
    assert failed_document.file_type == "txt"

    # Renamed to something with no matching extension at all — parser resolution must still work
    # on retry, since it now keys off file_type ("txt"), not this new name.
    renamed = document_repo.rename(failed_document.id, "completely-different-name")
    assert renamed.title == "completely-different-name"
    db_session.commit()

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(renamed)
    db_session.commit()

    assert retried_document.status == "indexed"
    assert retried_document.chunk_count > 0


def test_ingest_cancelled_immediately_marks_document_failed_with_cancellation_message(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    service = _make_service(db_session)

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        with pytest.raises(IngestionCancelled):
            service.ingest(org_id, owner.id, "notes.txt", b"hello world", should_cancel=lambda: True)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    cancelled_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    # No dedicated "cancelled" state exists in the document_status enum (processing/indexed/
    # failed/archived) — "failed" is the closest fit, with the cancellation reason preserved in
    # error_message so a caller can still tell the two apart (see IngestionService._process).
    assert cancelled_document.status == "failed"
    assert "Cancelled by user" in cancelled_document.error_message


def test_multi_batch_document_persists_all_chunks_with_no_duplicates(db_session, monkeypatch):
    """Regression test for the production OOM fix: chunks are now embedded/persisted in batches
    (INGESTION_EMBED_BATCH_SIZE) instead of all at once, so a real multi-chunk document must still
    end up with exactly one chunk per ordinal, not gaps or duplicates from crossing a batch
    boundary."""
    monkeypatch.setattr("api.application.ingestion_service.INGESTION_EMBED_BATCH_SIZE", 2)

    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=5, chunk_overlap=0
    )
    db_session.commit()

    from api.infrastructure.chunking.chunker import TextChunker

    text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    expected_piece_count = len(TextChunker(chunk_size=5, chunk_overlap=0).split(text))
    assert expected_piece_count > 4  # must span at least 3 batches of 2 to be a real test

    service = _make_service(db_session)
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = service.ingest(org_id, owner.id, "notes.txt", text.encode())
    db_session.commit()

    chunks = ChunkRepository(db_session).list_for_document(document.id, limit=1000, offset=0)
    assert document.status == "indexed"
    assert document.chunk_count == expected_piece_count
    assert len(chunks) == expected_piece_count
    assert sorted(c.ordinal for c in chunks) == list(range(expected_piece_count))  # no gaps, no dupes


def test_retry_after_partial_batch_failure_leaves_no_duplicate_or_stale_chunks(db_session, monkeypatch):
    """A batch already embedded and persisted before a later batch fails is now committed along
    with the rest of the failed job (matching the real worker's commit-on-failure behavior) --
    ChunkRepository.delete_for_document() at the start of every attempt is what makes a retry safe
    to re-run without ending up with duplicate ordinals from that earlier partial attempt."""
    monkeypatch.setattr("api.application.ingestion_service.INGESTION_EMBED_BATCH_SIZE", 2)

    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=5, chunk_overlap=0
    )
    db_session.commit()

    from api.infrastructure.chunking.chunker import TextChunker

    text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    expected_piece_count = len(TextChunker(chunk_size=5, chunk_overlap=0).split(text))
    assert expected_piece_count > 4

    service = _make_service(db_session)

    # First batch (pieces 0-1) succeeds; second batch (pieces 2-3) fails -- simulating a real
    # transient embedding-API failure partway through a multi-batch document.
    call_count = {"n": 0}

    def flaky_embed(texts, should_cancel=None):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("embedding API unavailable")
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    flaky_provider = MagicMock()
    flaky_provider.embed_documents.side_effect = flaky_embed

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=flaky_provider,
    ):
        with pytest.raises(RuntimeError):
            service.ingest(org_id, owner.id, "notes.txt", text.encode())
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    failed_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"
    # The first batch's 2 chunks were already committed before the second batch failed -- this
    # documents that real, intentional tradeoff (see INGESTION_EMBED_BATCH_SIZE's own comment),
    # not an assertion that nothing was written.
    assert chunk_repo.count_for_document(failed_document.id) == 2

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = service.retry(failed_document)
    db_session.commit()

    chunks = chunk_repo.list_for_document(retried_document.id, limit=1000, offset=0)
    assert retried_document.status == "indexed"
    assert retried_document.chunk_count == expected_piece_count
    assert len(chunks) == expected_piece_count  # not expected_piece_count + 2 stale leftovers
    assert sorted(c.ordinal for c in chunks) == list(range(expected_piece_count))


def test_embedding_settings_repository_reflects_whichever_provider_is_enabled(db_session):
    org = bootstrap_default_organization(db_session)
    db_session.commit()

    repo = EmbeddingSettingsRepository(db_session)
    assert repo.get(org.id) is None

    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "secret", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()
    assert repo.get(org.id).provider == "voyage"

    from api.infrastructure.repositories.embedding_provider_settings_repository import (
        EmbeddingProviderSettingsRepository,
    )

    EmbeddingProviderSettingsRepository(db_session).set_enabled(org.id, "voyage", False)
    db_session.commit()
    assert repo.get(org.id) is None
