import threading
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.config import config
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.orm import IngestionJob as IngestionJobModel
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository


@pytest.fixture()
def session_factory(postgres_url):
    engine = create_engine(postgres_url)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _owner_and_org(db_session):
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org = OrganizationRepository(db_session).get_by_slug("default")
    return owner, org


def _statement_timeout_ms(db_session) -> int:
    # pg_settings.setting reports the raw millisecond value for statement_timeout, unlike
    # SHOW/current_setting() which pretty-print it with a unit suffix (e.g. "3min") -- see
    # IngestionJobRepository.create()'s own comment for why this needs checking precisely.
    return int(db_session.execute(text("SELECT setting FROM pg_settings WHERE name = 'statement_timeout'")).scalar())


def test_create_with_payload_relaxes_statement_timeout_for_that_transaction_only(db_session):
    """Regression test: a large upload's raw bytes ride along on create()'s INSERT, which can
    legitimately take longer than the connection's normal statement_timeout -- see
    DB_STATEMENT_TIMEOUT_MS_LARGE_PAYLOAD_DEFAULT's comment for the production incident (a real
    ~80MB upload's INSERT alone exceeded the 15s default and was cancelled by Postgres). The SET
    LOCAL must be scoped to just that one transaction, not leak into later ones on the same
    connection -- verified here by checking a fresh transaction afterwards reverts to baseline."""
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    baseline = _statement_timeout_ms(db_session)

    ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id, payload=b"x" * 10)
    assert _statement_timeout_ms(db_session) == config.db_statement_timeout_ms_large_payload
    db_session.commit()

    # A fresh transaction on the same connection must not inherit the relaxed timeout.
    assert _statement_timeout_ms(db_session) == baseline


def test_create_without_payload_does_not_relax_statement_timeout(db_session):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    baseline = _statement_timeout_ms(db_session)

    ingestion_jobs.create(org.id, type="crawl", triggered_by=owner.id)

    assert _statement_timeout_ms(db_session) == baseline


def test_claim_next_queued_returns_none_when_empty(db_session):
    assert IngestionJobRepository(db_session).claim_next_queued("worker-1") is None


def test_claim_next_queued_claims_oldest_row_and_sets_claim_fields(db_session):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    older = ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()
    ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()

    claimed = ingestion_jobs.claim_next_queued("worker-1")

    assert claimed.id == older.id
    assert claimed.status == "processing"
    assert claimed.claimed_by == "worker-1"
    assert claimed.claimed_at is not None
    assert claimed.started_at is not None


def test_claim_next_queued_never_reclaims_a_processing_row(db_session, session_factory):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()

    first = ingestion_jobs.claim_next_queued("worker-1")
    assert first.id == job.id

    other_session = session_factory()
    second = IngestionJobRepository(other_session).claim_next_queued("worker-2")
    assert second is None
    other_session.close()


def test_two_concurrent_claimers_never_get_the_same_row(db_session, session_factory):
    owner, org = _owner_and_org(db_session)
    job_a = IngestionJobRepository(db_session).create(org.id, type="upload", triggered_by=owner.id)
    job_b = IngestionJobRepository(db_session).create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()

    results = []
    barrier = threading.Barrier(2)

    def claim(worker_id):
        session = session_factory()
        barrier.wait(timeout=5)
        claimed = IngestionJobRepository(session).claim_next_queued(worker_id)
        results.append(claimed.id if claimed is not None else None)
        session.close()

    threads = [threading.Thread(target=claim, args=(f"worker-{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert set(results) == {job_a.id, job_b.id}


def test_claim_next_queued_skips_a_locked_row_instead_of_blocking(db_session, session_factory):
    """Proves skip_locked=True is actually in effect, not just FOR UPDATE's default blocking
    behavior -- with only one queued row, held open (locked, uncommitted) on another connection,
    a concurrent claim must return None quickly rather than wait for that lock to release."""
    owner, org = _owner_and_org(db_session)
    job = IngestionJobRepository(db_session).create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()

    holder_session = session_factory()
    holder_session.execute(
        text("SELECT id FROM ingestion_jobs WHERE id = :id FOR UPDATE"), {"id": str(job.id)}
    )

    claimer_session = session_factory()
    start = time.monotonic()
    result = IngestionJobRepository(claimer_session).claim_next_queued("worker-2")
    elapsed = time.monotonic() - start
    claimer_session.close()

    assert result is None
    assert elapsed < 2.0, "claim_next_queued blocked on the locked row instead of skipping it"

    holder_session.rollback()
    holder_session.close()

    # Now that the lock is released, the row is claimable again.
    freed = IngestionJobRepository(db_session).claim_next_queued("worker-3")
    assert freed.id == job.id


def test_is_cancellation_requested_reflects_the_column(db_session):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()

    assert ingestion_jobs.is_cancellation_requested(job.id) is False

    model = db_session.get(IngestionJobModel, job.id)
    model.cancel_requested = True
    db_session.commit()

    assert ingestion_jobs.is_cancellation_requested(job.id) is True


def test_is_cancellation_requested_false_for_unknown_job(db_session):
    assert IngestionJobRepository(db_session).is_cancellation_requested(uuid4()) is False


def test_get_and_clear_payload(db_session):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id, payload=b"hello world")
    db_session.commit()

    assert ingestion_jobs.get_payload(job.id) == b"hello world"

    ingestion_jobs.clear_payload(job.id)
    db_session.commit()

    assert ingestion_jobs.get_payload(job.id) is None


def test_set_parts_total_and_increment_helpers(db_session):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org.id, type="upload", triggered_by=owner.id)
    db_session.commit()

    doc_id = uuid4()
    ingestion_jobs.set_parts_total(job.id, 3)
    ingestion_jobs.increment_parts_completed(job.id, doc_id)
    ingestion_jobs.increment_parts_failed(job.id)
    db_session.commit()

    refreshed = ingestion_jobs.get(job.id)
    assert refreshed.parts_total == 3
    assert refreshed.parts_completed == 1
    assert refreshed.parts_failed == 1
    assert refreshed.document_ids == [str(doc_id)]


def test_set_page_status(db_session):
    owner, org = _owner_and_org(db_session)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(org.id, type="crawl", triggered_by=owner.id)
    db_session.commit()

    doc_id = uuid4()
    ingestion_jobs.set_page_status(job.id, "https://example.com/a", "completed", doc_id, None)
    ingestion_jobs.set_page_status(job.id, "https://example.com/b", "failed", None, "boom")
    db_session.commit()

    refreshed = ingestion_jobs.get(job.id)
    assert refreshed.pages["https://example.com/a"] == {
        "status": "completed",
        "document_id": str(doc_id),
        "error": None,
    }
    assert refreshed.pages["https://example.com/b"] == {"status": "failed", "document_id": None, "error": "boom"}
