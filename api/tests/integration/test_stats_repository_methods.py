from datetime import datetime, timedelta, timezone
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
from api.infrastructure.repositories.embedding_provider_settings_repository import EmbeddingProviderSettingsRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.query_repository import QueryRepository
from api.tests.integration.conftest import seed_active_embedding_provider

# Real-DB coverage for the aggregate SQL these repository methods run (joins, group-by, org
# scoping) — the kind of query logic a mocked unit test can't actually verify.


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


def _ingest_document(db_session, org_id, owner_id, filename="notes.txt"):
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    ingestion_service = IngestionService(document_repo, chunk_repo, EmbeddingSettingsRepository(db_session))
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    with patch("api.application.ingestion_service.EmbeddingProviderRegistry.resolve", return_value=provider):
        document = ingestion_service.ingest(org_id, owner_id, filename, ("abc " * 30).encode())
    db_session.commit()
    return document, chunk_repo.list_for_document(document.id, limit=10, offset=0)


def test_chunk_count_for_org_does_not_leak_other_orgs(db_session, org_id, owner_id):
    # seed_active_embedding_provider always resolves to the idempotent default org (see its own
    # docstring) — a genuinely separate second org needs its own explicit creation + config.
    other_org = OrganizationRepository(db_session).create("Other Org", "other-org")
    embedding_settings = EmbeddingProviderSettingsRepository(db_session)
    embedding_settings.upsert_config(other_org.id, "voyage", "voyage-3", "other-key", None, EMBEDDING_DIM, 20, 5)
    embedding_settings.set_enabled(other_org.id, "voyage", True)
    db_session.commit()

    _document, chunks = _ingest_document(db_session, org_id, owner_id)
    _other_document, other_chunks = _ingest_document(db_session, other_org.id, owner_id, filename="other-org-notes.txt")

    chunk_repo = ChunkRepository(db_session)
    assert chunk_repo.count_for_org(org_id) == len(chunks)
    assert chunk_repo.count_for_org(other_org.id) == len(other_chunks)
    assert chunk_repo.count_for_org(uuid4()) == 0


def test_count_since_and_avg_latency_since(db_session, org_id, owner_id):
    _document, chunks = _ingest_document(db_session, org_id, owner_id)
    query_repo = QueryRepository(db_session)
    history = QueryHistoryService(query_repo)
    scored = [ScoredChunk(id=chunk.id, document_id=chunk.document_id, ordinal=chunk.ordinal, content=chunk.content, score=0.9) for chunk in chunks]

    history.record(org_id, owner_id, "first query", 100, scored)
    history.record(org_id, owner_id, "second query", 200, scored)
    db_session.commit()

    since = datetime.now(timezone.utc) - timedelta(days=1)
    assert query_repo.count_since(org_id, since) == 2
    assert query_repo.avg_latency_since(org_id, since) == 150.0

    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert query_repo.count_since(org_id, future) == 0
    assert query_repo.avg_latency_since(org_id, future) is None


def test_most_retrieved_documents_ranks_by_retrieval_count(db_session, org_id, owner_id):
    popular_doc, popular_chunks = _ingest_document(db_session, org_id, owner_id, filename="popular.txt")
    quiet_doc, quiet_chunks = _ingest_document(db_session, org_id, owner_id, filename="quiet.txt")
    query_repo = QueryRepository(db_session)
    history = QueryHistoryService(query_repo)

    popular_scored = [ScoredChunk(id=c.id, document_id=c.document_id, ordinal=c.ordinal, content=c.content, score=0.9) for c in popular_chunks]
    quiet_scored = [ScoredChunk(id=c.id, document_id=c.document_id, ordinal=c.ordinal, content=c.content, score=0.5) for c in quiet_chunks]

    history.record(org_id, owner_id, "q1", 10, popular_scored)
    history.record(org_id, owner_id, "q2", 10, popular_scored)
    history.record(org_id, owner_id, "q3", 10, quiet_scored)
    db_session.commit()

    ranked = query_repo.most_retrieved_documents(org_id, limit=5)
    # retrieval_count is a count of query_results rows (one per retrieved chunk per query), not
    # distinct queries — the popular doc was queried twice (2x its chunk count), the quiet doc once.
    assert ranked[0][0] == popular_doc.id
    assert ranked[0][2] == 2 * len(popular_chunks)
    assert ranked[1][0] == quiet_doc.id
    assert ranked[1][2] == len(quiet_chunks)


def test_retrieval_stats_for_document(db_session, org_id, owner_id):
    document, chunks = _ingest_document(db_session, org_id, owner_id)
    query_repo = QueryRepository(db_session)
    history = QueryHistoryService(query_repo)
    scored = [ScoredChunk(id=c.id, document_id=c.document_id, ordinal=c.ordinal, content=c.content, score=0.8) for c in chunks]

    history.record(org_id, owner_id, "q1", 10, scored)
    db_session.commit()

    count, avg_similarity = query_repo.retrieval_stats_for_document(document.id)
    assert count == len(chunks)
    assert avg_similarity == pytest.approx(0.8)

    other_count, other_avg = query_repo.retrieval_stats_for_document(uuid4())
    assert other_count == 0
    assert other_avg is None
