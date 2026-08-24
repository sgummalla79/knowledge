from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from api.application.document_service import DocumentService
from api.application.ingestion_service import IngestionService
from api.constants import EMBEDDING_DIM
from api.domain import error_codes
from api.domain.errors import NotFoundError, ValidationError
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.tests.integration.conftest import seed_active_embedding_provider

# Actual ingestion *execution* (upload/retry/crawl, split-PDF, cancellation) is covered by
# api/ingestion_worker/tests/ now — document_service.py itself only enqueues a queued row and
# reads/cancels one; that's what this file tests.


def _owner(db_session):
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get()


def _fake_provider():
    from unittest.mock import MagicMock

    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _ingest(document_repo, chunk_repo, db_session, org_id, owner_id, filename="notes.txt"):
    ingestion_service = IngestionService(
        document_repo, chunk_repo, EmbeddingSettingsRepository(db_session)
    )
    text = "abcdefghijklmnopqrstuvwxyz" * 3
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        document = ingestion_service.ingest(org_id, owner_id, filename, text.encode())
    db_session.commit()
    return document


def _ingest_failing(document_repo, chunk_repo, db_session, org_id, owner_id, filename="notes.txt"):
    ingestion_service = IngestionService(
        document_repo, chunk_repo, EmbeddingSettingsRepository(db_session)
    )
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        with pytest.raises(RuntimeError):
            ingestion_service.ingest(org_id, owner_id, filename, b"hello world")
    db_session.commit()
    return document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]


def test_start_ingestion_enqueues_a_queued_row_and_returns_its_id(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()
    category = CategoryRepository(db_session).create(org_id, name="Guides", slug="guides", description=None)
    db_session.commit()

    ingestion_jobs = IngestionJobRepository(db_session)
    service = DocumentService(DocumentRepository(db_session), ChunkRepository(db_session), ingestion_jobs)
    job_id = service.start_ingestion(org_id, owner.id, "notes.txt", b"hello world", category_id=category.id)

    job = ingestion_jobs.get(UUID(job_id))
    assert job.status == "queued"
    assert job.payload_filename == "notes.txt"
    assert job.category_id == category.id
    assert ingestion_jobs.get_payload(job.id) == b"hello world"


def test_start_retry_enqueues_a_queued_reindex_row(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()
    failed_document = _ingest_failing(document_repo, chunk_repo, db_session, org_id, owner.id)

    ingestion_jobs = IngestionJobRepository(db_session)
    service = DocumentService(document_repo, chunk_repo, ingestion_jobs)
    job_id = service.start_retry(org_id, failed_document.id, owner.id)

    job = ingestion_jobs.get(UUID(job_id))
    assert job.status == "queued"
    assert job.type == "reindex"
    assert job.document_id == failed_document.id


def test_start_crawl_enqueues_a_queued_row_with_crawl_fields(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    ingestion_jobs = IngestionJobRepository(db_session)
    service = DocumentService(DocumentRepository(db_session), ChunkRepository(db_session), ingestion_jobs)
    job_id = service.start_crawl(org_id, owner.id, "https://example.com", 5, "https://example.com/docs")

    job = ingestion_jobs.get(UUID(job_id))
    assert job.status == "queued"
    assert job.type == "crawl"
    assert job.crawl_url == "https://example.com"
    assert job.crawl_max_pages == 5
    assert job.crawl_scope_prefix == "https://example.com/docs"


@pytest.mark.parametrize(
    "raw_status,expected",
    [("queued", "pending"), ("processing", "running"), ("indexed", "completed"), ("failed", "failed")],
)
def test_get_job_status_maps_status_vocabulary(db_session, raw_status, expected):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org_id, type="upload", triggered_by=owner.id)
    ingestion_jobs.update_status(job.id, raw_status)
    db_session.commit()

    service = DocumentService(DocumentRepository(db_session), ChunkRepository(db_session), ingestion_jobs)
    assert service.get_job_status(org_id, str(job.id))["status"] == expected


def test_get_job_status_returns_error_message_and_progress_fields(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org_id, type="upload", triggered_by=owner.id)
    ingestion_jobs.update_status(job.id, "failed", error_message="boom")
    ingestion_jobs.set_parts_total(job.id, 2)
    ingestion_jobs.increment_parts_completed(job.id, uuid4())
    ingestion_jobs.increment_parts_failed(job.id)
    db_session.commit()

    service = DocumentService(DocumentRepository(db_session), ChunkRepository(db_session), ingestion_jobs)
    status = service.get_job_status(org_id, str(job.id))
    assert status["error"] == "boom"
    assert status["parts_total"] == 2
    assert status["parts_completed"] == 1
    assert status["parts_failed"] == 1
    assert len(status["document_ids"]) == 1


def test_get_job_status_missing_job_raises_job_not_found(db_session):
    service = DocumentService(
        DocumentRepository(db_session), ChunkRepository(db_session), IngestionJobRepository(db_session)
    )
    with pytest.raises(NotFoundError) as exc_info:
        service.get_job_status(uuid4(), str(uuid4()))
    assert exc_info.value.code == error_codes.JOB_NOT_FOUND


def test_get_crawl_job_status_returns_pages(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org_id, type="crawl", triggered_by=owner.id, crawl_url="https://example.com/a")
    ingestion_jobs.update_status(job.id, "indexed")
    ingestion_jobs.set_page_status(job.id, "https://example.com/a", "completed", uuid4(), None)
    db_session.commit()

    service = DocumentService(DocumentRepository(db_session), ChunkRepository(db_session), ingestion_jobs)
    status = service.get_crawl_job_status(org_id, str(job.id))
    assert status["status"] == "completed"
    assert status["seed_url"] == "https://example.com/a"
    assert status["pages"]["https://example.com/a"]["status"] == "completed"


def test_cancel_job_missing_job_raises_job_not_found(db_session):
    service = DocumentService(
        DocumentRepository(db_session), ChunkRepository(db_session), IngestionJobRepository(db_session)
    )
    with pytest.raises(NotFoundError) as exc_info:
        service.cancel_job(uuid4(), "does-not-exist")
    assert exc_info.value.code == error_codes.JOB_NOT_FOUND


def test_cancel_job_sets_cancel_requested(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org_id, type="upload", triggered_by=owner.id)
    db_session.commit()

    service = DocumentService(DocumentRepository(db_session), ChunkRepository(db_session), ingestion_jobs)
    service.cancel_job(org_id, str(job.id))

    refreshed = ingestion_jobs.get(job.id)
    assert refreshed.cancel_requested is True


def test_delete_document_removes_chunks(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)
    assert chunk_repo.count_for_document(document.id) > 0

    DocumentService(document_repo, chunk_repo).delete_document(org_id, document.id)
    db_session.commit()

    assert document_repo.get(document.id) is None
    assert chunk_repo.count_for_document(document.id) == 0


def test_delete_document_from_wrong_org_raises_document_not_found(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, chunk_repo).delete_document(uuid4(), document.id)
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND

    # Nothing should have been touched — still exists, still belongs to org_id.
    assert document_repo.get(document.id) is not None


def test_delete_document_missing_document_raises_document_not_found(db_session):
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, chunk_repo).delete_document(uuid4(), uuid4())
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND


def test_start_retry_on_non_failed_document_raises_document_not_retryable(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)  # indexed
    assert document.status == "indexed"

    with pytest.raises(ValidationError) as exc_info:
        DocumentService(document_repo, chunk_repo, IngestionJobRepository(db_session)).start_retry(
            org_id, document.id, owner.id
        )
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_RETRYABLE


def test_start_retry_from_wrong_org_raises_document_not_found(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    failed_document = _ingest_failing(document_repo, chunk_repo, db_session, org_id, owner.id)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, chunk_repo, IngestionJobRepository(db_session)).start_retry(
            uuid4(), failed_document.id, owner.id
        )
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND


def test_rename_document_updates_title(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)

    renamed = DocumentService(document_repo, chunk_repo).rename_document(org_id, document.id, "renamed.txt")
    db_session.commit()

    assert renamed.title == "renamed.txt"
    assert document_repo.get(document.id).title == "renamed.txt"


def test_rename_document_from_wrong_org_raises_document_not_found(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, chunk_repo).rename_document(uuid4(), document.id, "renamed.txt")
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND
    assert document_repo.get(document.id).title != "renamed.txt"


def test_rename_document_missing_document_raises_document_not_found(db_session):
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    with pytest.raises(NotFoundError) as exc_info:
        DocumentService(document_repo, chunk_repo).rename_document(uuid4(), uuid4(), "x.txt")
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND


def test_update_metadata_updates_category_and_type(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    category_repo = CategoryRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    category = category_repo.create(org_id, name="Guides", slug="guides", description=None)
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)

    service = DocumentService(document_repo, chunk_repo, category_repo=category_repo)
    updated = service.update_metadata(org_id, document.id, category.id, "article")
    db_session.commit()

    assert updated.category_id == category.id
    assert updated.type == "article"
    stored = document_repo.get(document.id)
    assert stored.category_id == category.id
    assert stored.type == "article"


def test_update_metadata_can_clear_category(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    category_repo = CategoryRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    category = category_repo.create(org_id, name="Guides", slug="guides", description=None)
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)
    service = DocumentService(document_repo, chunk_repo, category_repo=category_repo)
    service.update_metadata(org_id, document.id, category.id, document.type)
    db_session.commit()

    updated = service.update_metadata(org_id, document.id, None, document.type)
    db_session.commit()

    assert updated.category_id is None
    assert document_repo.get(document.id).category_id is None


def test_update_metadata_from_wrong_org_raises_document_not_found(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    category_repo = CategoryRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)

    service = DocumentService(document_repo, chunk_repo, category_repo=category_repo)
    with pytest.raises(NotFoundError) as exc_info:
        service.update_metadata(uuid4(), document.id, None, "article")
    assert exc_info.value.code == error_codes.DOCUMENT_NOT_FOUND
    assert document_repo.get(document.id).type != "article"


def test_update_metadata_with_foreign_category_raises_category_not_found(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    category_repo = CategoryRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    other_org = OrganizationRepository(db_session).create("Other Org", "other-org")
    foreign_category = category_repo.create(other_org.id, name="Foreign", slug="foreign", description=None)
    db_session.commit()

    document = _ingest(document_repo, chunk_repo, db_session, org_id, owner.id)

    service = DocumentService(document_repo, chunk_repo, category_repo=category_repo)
    with pytest.raises(NotFoundError) as exc_info:
        service.update_metadata(org_id, document.id, foreign_category.id, document.type)
    assert exc_info.value.code == error_codes.CATEGORY_NOT_FOUND
    assert document_repo.get(document.id).category_id != foreign_category.id


def test_start_retry_allows_a_document_cancelled_mid_ingestion(db_session):
    owner = _owner(db_session)
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    db_session.commit()

    ingestion_service = IngestionService(
        document_repo, chunk_repo, EmbeddingSettingsRepository(db_session)
    )
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        with pytest.raises(Exception):
            ingestion_service.ingest(org_id, owner.id, "notes.txt", b"hello world", should_cancel=lambda: True)
    db_session.commit()

    # No dedicated "cancelled" state exists in the document_status enum — a cancellation is
    # recorded as "failed" with the reason in error_message (see IngestionService._process).
    cancelled_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    assert cancelled_document.status == "failed"

    # Retryable just like any other failed document.
    job_id = DocumentService(document_repo, chunk_repo, IngestionJobRepository(db_session)).start_retry(
        org_id, cancelled_document.id, owner.id
    )
    assert job_id is not None
