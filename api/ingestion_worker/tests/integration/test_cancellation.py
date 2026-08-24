from unittest.mock import MagicMock, patch

from api.constants import EMBEDDING_DIM
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.ingestion_worker.tests.integration.conftest import seed_active_embedding_provider
from api.ingestion_worker.worker import IngestionJobWorker


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _owner(db_session):
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get()


def test_cancel_requested_before_claim_marks_job_and_document_failed(db_session, session_factory):
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
        cancel_requested=True,
    )
    db_session.commit()

    worker = IngestionJobWorker(session_factory=session_factory)
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve", return_value=_fake_provider()
    ):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "Cancelled by user."
    assert IngestionJobRepository(verify_session).get_payload(job.id) is None

    documents = DocumentRepository(verify_session).list_for_org(org_id, limit=10, offset=0, sort="-created_at")
    assert len(documents) == 1
    assert documents[0].status == "failed"
    verify_session.close()
