from unittest.mock import patch

from api.constants import EMBEDDING_DIM
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.ingestion_worker.tests.integration.conftest import seed_active_embedding_provider
from api.ingestion_worker.worker import IngestionJobWorker


def _owner(db_session):
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get()


def test_embedding_failure_marks_job_failed_with_error_message_and_clears_payload(db_session, session_factory):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(
        org_id,
        type="upload",
        triggered_by=owner.id,
        payload=b"hello world",
        payload_filename="notes.txt",
    )
    db_session.commit()

    worker = IngestionJobWorker(session_factory=session_factory)
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "embedding API unavailable"
    assert refreshed.finished_at is not None
    assert IngestionJobRepository(verify_session).get_payload(job.id) is None
    verify_session.close()


def test_retry_job_failure_marks_job_failed(db_session, session_factory):
    from unittest.mock import MagicMock

    from api.application.ingestion_service import IngestionService
    from api.infrastructure.repositories.chunk_repository import ChunkRepository
    from api.infrastructure.repositories.document_repository import DocumentRepository
    from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository

    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )

    def _fake_provider():
        provider = MagicMock()
        provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
        return provider

    document_repo = DocumentRepository(db_session)
    ingestion_service = IngestionService(document_repo, ChunkRepository(db_session), EmbeddingSettingsRepository(db_session))
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("embedding API unavailable"),
    ):
        try:
            ingestion_service.ingest(org_id, owner.id, "notes.txt", b"hello world")
        except Exception:
            pass
    db_session.commit()
    failed_document = document_repo.list_for_org(org_id, limit=10, offset=0, sort="-created_at")[0]
    assert failed_document.status == "failed"

    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org_id, type="reindex", document_id=failed_document.id, triggered_by=owner.id)
    db_session.commit()

    worker = IngestionJobWorker(session_factory=session_factory)
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=RuntimeError("still unavailable"),
    ):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "still unavailable"
    verify_session.close()
