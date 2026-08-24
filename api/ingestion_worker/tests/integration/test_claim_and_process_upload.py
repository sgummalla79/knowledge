from unittest.mock import MagicMock, patch

from api.constants import EMBEDDING_DIM
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.chunk_repository import ChunkRepository
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


def test_claim_and_process_upload_end_to_end(db_session, session_factory):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(
        org_id,
        type="upload",
        triggered_by=owner.id,
        payload=b"hello world, this is a test document",
        payload_filename="notes.txt",
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
    assert refreshed.status == "indexed"
    assert refreshed.document_id is not None
    assert refreshed.items_processed == 1
    assert refreshed.finished_at is not None
    assert refreshed.claimed_by is not None

    # Payload cleared -- this table never holds an upload's bytes longer than it takes to process.
    assert IngestionJobRepository(verify_session).get_payload(job.id) is None

    document = DocumentRepository(verify_session).get(refreshed.document_id)
    assert document.status == "indexed"
    chunks = ChunkRepository(verify_session).list_for_document(document.id, limit=100, offset=0)
    assert len(chunks) > 0
    verify_session.close()


def test_claim_and_process_one_returns_false_and_leaves_queue_empty_when_nothing_queued(db_session, session_factory):
    worker = IngestionJobWorker(session_factory=session_factory)
    assert worker.claim_and_process_one() is False
