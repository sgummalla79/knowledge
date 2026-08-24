from unittest.mock import MagicMock, patch

from api.constants import EMBEDDING_DIM
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.web.fetcher import FetchedPage
from api.ingestion_worker.tests.integration.conftest import seed_active_embedding_provider
from api.ingestion_worker.worker import IngestionJobWorker


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _owner(db_session):
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get()


def test_claim_and_process_crawl_single_page(db_session, session_factory):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(
        org_id,
        type="crawl",
        triggered_by=owner.id,
        crawl_url="https://example.com/a",
        crawl_max_pages=1,
    )
    db_session.commit()

    fake_fetcher = MagicMock()
    fake_fetcher.fetch.return_value = FetchedPage(
        content=b"<html><body><p>hello crawl page</p></body></html>", final_url="https://example.com/a"
    )

    worker = IngestionJobWorker(session_factory=session_factory)
    with (
        patch("api.ingestion_worker.worker.WebPageFetcher", return_value=fake_fetcher),
        patch("api.application.ingestion_service.EmbeddingProviderRegistry.resolve", return_value=_fake_provider()),
    ):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    assert refreshed.status == "indexed"
    assert refreshed.items_processed == 1
    assert refreshed.finished_at is not None
    assert refreshed.pages["https://example.com/a"]["status"] == "completed"
    assert refreshed.pages["https://example.com/a"]["document_id"] is not None
    verify_session.close()


def test_claim_and_process_crawl_page_failure_is_recorded(db_session, session_factory):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(
        org_id,
        type="crawl",
        triggered_by=owner.id,
        crawl_url="https://example.com/broken",
        crawl_max_pages=1,
    )
    db_session.commit()

    fake_fetcher = MagicMock()
    fake_fetcher.fetch.side_effect = RuntimeError("connection refused")

    worker = IngestionJobWorker(session_factory=session_factory)
    with patch("api.ingestion_worker.worker.WebPageFetcher", return_value=fake_fetcher):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    # The single page failed, so nothing completed -- items_processed stays 0, but the job itself
    # still reaches a terminal "indexed" state (a crawl with zero successful pages isn't treated
    # as a job-level failure -- same semantics WebCrawlService.crawl already has: per-page errors
    # are captured, not raised).
    assert refreshed.status == "indexed"
    assert refreshed.items_processed == 0
    assert refreshed.pages["https://example.com/broken"]["status"] == "failed"
    assert refreshed.pages["https://example.com/broken"]["error"] is not None
    verify_session.close()
