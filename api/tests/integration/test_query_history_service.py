from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.application.ingestion_service import IngestionService
from api.application.query_history_service import QueryHistoryService
from api.constants import EMBEDDING_DIM
from api.domain.entities import ScoredChunk
from api.infrastructure.auth.bootstrap import bootstrap_default_identity, bootstrap_default_organization
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.infrastructure.storage.upload_storage import UploadStorage
from api.tests.integration.conftest import seed_active_embedding_provider


@pytest.fixture()
def org_id(db_session):
    return seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )


@pytest.fixture()
def owner_id(db_session):
    bootstrap_default_organization(db_session)
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get().id


def _real_chunks(db_session, storage, org_id, owner_id):
    """Ingests one document for real chunk rows to satisfy query_results' FK on chunk_id."""
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    ingestion_service = IngestionService(
        document_repo, chunk_repo, EmbeddingSettingsRepository(db_session), storage
    )
    source_path = "src/notes.txt"
    storage.save_bytes(source_path, ("abc " * 30).encode())
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve", return_value=provider
    ):
        document = ingestion_service.ingest(org_id, owner_id, "notes.txt", source_path)
    db_session.commit()
    return chunk_repo.list_for_document(document.id, limit=10, offset=0)


@pytest.fixture()
def storage(tmp_path):
    return UploadStorage(tmp_path)


def test_record_persists_query_and_results(db_session, storage, org_id, owner_id):
    repo = QueryRepository(db_session)
    service = QueryHistoryService(repo)
    real_chunks = _real_chunks(db_session, storage, org_id, owner_id)
    assert len(real_chunks) > 0
    chunks = [
        ScoredChunk(id=chunk.id, document_id=chunk.document_id, ordinal=chunk.ordinal, content=chunk.content, score=0.9)
        for chunk in real_chunks
    ]

    service.record(org_id, owner_id, "vector databases", 42, chunks)
    db_session.commit()

    history = repo.list_by_org(org_id, limit=10, offset=0)
    assert len(history) == 1
    assert history[0].query_text == "vector databases"
    assert history[0].user_id == owner_id
    assert history[0].latency_ms == 42
    assert history[0].result_count == len(chunks)


def test_record_with_no_chunks_still_persists_zero_result_query(db_session, org_id):
    repo = QueryRepository(db_session)
    service = QueryHistoryService(repo)

    service.record(org_id, None, "no matches", 10, [])
    db_session.commit()

    history = repo.list_by_org(org_id, limit=10, offset=0)
    assert len(history) == 1
    assert history[0].result_count == 0
    assert history[0].user_id is None


def test_record_swallows_failure_and_leaves_session_usable(db_session, org_id):
    """A chunk_id that doesn't exist in `chunks` violates record_results' FK — record() must roll
    back and swallow rather than leave the session's transaction broken for whatever runs next
    (see the try/except's rollback in query_history_service.py, and A.5's "best-effort" framing)."""
    repo = QueryRepository(db_session)
    service = QueryHistoryService(repo)
    bogus_chunk = ScoredChunk(id=uuid4(), document_id=uuid4(), ordinal=0, content="x", score=0.5)

    service.record(org_id, None, "will fail", 5, [bogus_chunk])

    # Session must still be usable — proves the rollback actually happened.
    db_session.commit()
    assert repo.list_by_org(org_id, limit=10, offset=0) == []
