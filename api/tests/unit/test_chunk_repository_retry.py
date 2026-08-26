import time
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from api.constants import INGESTION_BULK_INSERT_MAX_ATTEMPTS
from api.infrastructure.repositories.chunk_repository import ChunkRepository


class _FakeOrig:
    def __init__(self, pgcode):
        self.pgcode = pgcode


def _query_canceled():
    return OperationalError("INSERT ...", {}, _FakeOrig("57014"))


def _unique_violation():
    return OperationalError("INSERT ...", {}, _FakeOrig("23505"))


def _make_session():
    session = MagicMock()
    # A bare MagicMock's __exit__ returns a truthy MagicMock by default, which would silently
    # *suppress* any exception raised inside the `with` block -- the opposite of how a real
    # SQLAlchemy SessionTransaction behaves. Pinned to False so a flush() failure actually
    # propagates to bulk_create's except clause, same as against a real session.
    session.begin_nested.return_value.__exit__.return_value = False
    return session


def test_bulk_create_retries_once_on_query_canceled_then_succeeds(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    session = _make_session()
    session.flush.side_effect = [_query_canceled(), None]
    repo = ChunkRepository(session)

    repo.bulk_create("doc-id", "org-id", "model-id", [(0, "text", 1, [0.0])])

    assert session.flush.call_count == 2


def test_bulk_create_does_not_retry_other_operational_errors(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    session = _make_session()
    session.flush.side_effect = _unique_violation()
    repo = ChunkRepository(session)

    with pytest.raises(OperationalError):
        repo.bulk_create("doc-id", "org-id", "model-id", [(0, "text", 1, [0.0])])

    assert session.flush.call_count == 1


def test_bulk_create_raises_after_exhausting_retries(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    session = _make_session()
    session.flush.side_effect = _query_canceled()
    repo = ChunkRepository(session)

    with pytest.raises(OperationalError):
        repo.bulk_create("doc-id", "org-id", "model-id", [(0, "text", 1, [0.0])])

    assert session.flush.call_count == INGESTION_BULK_INSERT_MAX_ATTEMPTS
    # One sleep between each attempt, none after the last (final failure raises immediately).
    assert len(sleeps) == INGESTION_BULK_INSERT_MAX_ATTEMPTS - 1
