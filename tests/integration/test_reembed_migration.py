from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.cli import reembed_chunks
from app.constants import EMBEDDING_DIM

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# This test needs precise control over which migration the database is stopped at (0006, before
# the cutover), so it uses its own dedicated container rather than conftest.py's session-scoped
# `postgres_url` fixture, which is already upgraded to "head".


def _alembic_config(url: str) -> AlembicConfig:
    cfg = AlembicConfig(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture()
def stopped_at_0006():
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        url = postgres.get_connection_url()
        cfg = _alembic_config(url)
        command.upgrade(cfg, "0006")
        engine = sa.create_engine(url)
        session_factory = sessionmaker(bind=engine)
        yield cfg, engine, session_factory
        engine.dispose()


def _seed_chunks_missing_embedding_new(session_factory, count: int) -> None:
    """Rows with `embedding` set (simulating already-ingested data) but `embedding_new` still
    NULL — reproduces exactly the "needs backfilling" state migration 0006 leaves existing data
    in. Uses raw SQL rather than the ORM-backed repositories deliberately: this fixture freezes
    the database at migration "0006", but the ORM models are written against the current head
    schema (e.g. documents.raw_file_bytes/error_message, added in migration 0008) — going through
    DocumentRepository etc. here would insert columns that don't exist yet at "0006" and fail.
    Raw SQL keeps this test's seed data honestly scoped to what "0006" actually looks like,
    independent of how the schema evolves later."""
    session = session_factory()
    try:
        library_id = uuid4()
        document_id = uuid4()
        session.execute(
            sa.text("INSERT INTO libraries (id, name) VALUES (:id, :name)"),
            {"id": library_id, "name": f"reembed-test-{library_id}"},
        )
        session.execute(
            sa.text(
                "INSERT INTO documents (id, library_id, source_filename, file_type, content_hash, status) "
                "VALUES (:id, :library_id, 'notes.txt', 'txt', 'hash', 'completed')"
            ),
            {"id": document_id, "library_id": library_id},
        )
        for index in range(count):
            vector_literal = "[" + ",".join(["0.1"] * EMBEDDING_DIM) + "]"
            session.execute(
                sa.text(
                    "INSERT INTO chunks (id, document_id, library_id, chunk_index, content, embedding) "
                    "VALUES (:id, :document_id, :library_id, :chunk_index, :content, CAST(:embedding AS vector))"
                ),
                {
                    "id": uuid4(),
                    "document_id": document_id,
                    "library_id": library_id,
                    "chunk_index": index,
                    "content": f"chunk-{index}",
                    "embedding": vector_literal,
                },
            )
        session.commit()
    finally:
        session.close()


def _fake_provider(dim: int):
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts: [[0.2] * dim for _ in texts]
    return provider


def test_reembed_backfills_all_rows_then_cutover_succeeds(stopped_at_0006):
    cfg, engine, session_factory = stopped_at_0006
    _seed_chunks_missing_embedding_new(session_factory, count=3)

    with patch("app.cli.SessionLocal", session_factory), patch(
        "app.cli.EmbeddingProviderRegistry.resolve", return_value=_fake_provider(EMBEDDING_DIM)
    ):
        total = reembed_chunks(provider="ollama", model="nomic-embed-text")
    assert total == 3

    with engine.connect() as conn:
        missing = conn.execute(
            sa.text("SELECT count(*) FROM chunks WHERE embedding_new IS NULL")
        ).scalar()
    assert missing == 0

    command.upgrade(cfg, "0007")

    with engine.connect() as conn:
        row_count = conn.execute(sa.text("SELECT count(*) FROM chunks")).scalar()
        index_exists = conn.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
        ).scalar()
        column_names = {
            row[0]
            for row in conn.execute(
                sa.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'chunks'")
            )
        }
    assert row_count == 3
    assert index_exists == 1
    assert "embedding" in column_names
    assert "embedding_new" not in column_names


def test_reembed_is_resumable_across_two_runs(stopped_at_0006):
    cfg, engine, session_factory = stopped_at_0006
    _seed_chunks_missing_embedding_new(session_factory, count=5)

    fake_provider = _fake_provider(EMBEDDING_DIM)
    with patch("app.cli.SessionLocal", session_factory), patch(
        "app.cli.EmbeddingProviderRegistry.resolve", return_value=fake_provider
    ):
        first_run_total = reembed_chunks(provider="ollama", model="nomic-embed-text", batch_size=2)
        # A second run should process zero additional rows — everything is already backfilled.
        second_run_total = reembed_chunks(provider="ollama", model="nomic-embed-text", batch_size=2)

    assert first_run_total == 5
    assert second_run_total == 0


def test_cutover_guard_raises_when_backfill_incomplete(stopped_at_0006):
    cfg, engine, session_factory = stopped_at_0006
    _seed_chunks_missing_embedding_new(session_factory, count=1)
    # embedding_new deliberately left NULL — no reembed_chunks() call before the cutover attempt.

    with pytest.raises(Exception, match="reembed incomplete"):
        command.upgrade(cfg, "0007")
