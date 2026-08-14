"""Regression coverage for a real incident: after EmbeddingProviderConfigService.enable() resizes
chunks.embedding to a non-default dimension, a real ChunkRepository.bulk_create() insert at that
new dimension must actually succeed.

Every other integration test configures a provider via EmbeddingProviderSettingsRepository.
upsert_config() directly, bypassing EmbeddingProviderConfigService.enable() entirely — so none of
them ever exercised resize_embedding_column() against a real database. That gap is exactly how
this shipped: the ORM's Chunk.embedding column used to be declared Vector(EMBEDDING_DIM) — a
Python-side constant fixed at process-import time — so resize_embedding_column()'s raw `ALTER
TABLE ... TYPE vector(N)` correctly changed the live Postgres column, but pgvector's client-side
bind_processor kept validating inserts against the stale compiled-in dimension (768) for the
lifetime of the process. A production container restart between saving 1024-dim Voyage settings
and the next upload silently reverted enforcement back to 768, rejecting perfectly valid 1024-dim
vectors with "expected 768 dimensions, not 1024" even though the real column was already
vector(1024). Fixed by making the ORM column dimensionless (Vector()) and deferring all
enforcement to Postgres's own column constraint, which is always accurate regardless of process
lifetime.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.application.embedding_provider_settings_service import EmbeddingProviderConfigService
from app.constants import EMBEDDING_DIM
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.embedding_provider_settings_repository import (
    EmbeddingProviderSettingsRepository,
)
from app.infrastructure.repositories.library_repository import LibraryRepository


def _mock_provider(vector):
    provider = MagicMock()
    provider.embed_query.return_value = vector
    return provider


@pytest.fixture()
def restore_embedding_dim(db_session):
    """The Postgres container (and its schema) is session-scoped across the whole test run —
    db_session only TRUNCATEs data between tests, it doesn't undo DDL. This test's whole point is
    to really run resize_embedding_column() against chunks.embedding, so it must put the column
    back the way every other integration test assumes it is (EMBEDDING_DIM) once it's done,
    otherwise every test after this one that inserts a 768-dim fixture vector starts failing."""
    yield
    # A resized column can't be shrunk back while it still holds data at the wider dimension —
    # Postgres validates existing rows against the new type during ALTER COLUMN TYPE, same as it
    # would for any real "switch models" transition (which is exactly why
    # EmbeddingProviderConfigService.enable() only ever allows a dimension change while chunks is empty).
    db_session.execute(text("DELETE FROM chunks"))
    ChunkRepository(db_session).resize_embedding_column(EMBEDDING_DIM)
    db_session.commit()


def test_resize_to_non_default_dimension_then_real_insert_succeeds(db_session, restore_embedding_dim):
    provider_settings_repo = EmbeddingProviderSettingsRepository(db_session)
    embedding_provider_service = EmbeddingProviderConfigService(
        provider_settings_repo, ChunkRepository(db_session), LibraryRepository(db_session)
    )

    # A dimension nothing else in this DB has ever used — if the ORM's column type were still
    # hardcoded to the historical default, this insert below would fail exactly like production did.
    new_dimension = 1024
    with patch(
        "app.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * new_dimension),
    ):
        embedding_provider_service.update_config(
            "voyage", "voyage-4-lite", "test-key", None, new_dimension, 800, 100
        )
        db_session.commit()
        embedding_provider_service.enable("voyage")
    db_session.commit()

    library = LibraryRepository(db_session).create(name="resize-test", description=None)
    document = DocumentRepository(db_session).create(
        library_id=library.id,
        source_filename="notes.txt",
        file_type="txt",
        content_hash="deadbeef",
        status="processing",
    )
    db_session.commit()

    chunk_repo = ChunkRepository(db_session)
    # This is the real regression check: inserting a genuinely new_dimension-length vector via the
    # ORM must not raise pgvector's client-side "expected N dimensions" ValueError.
    chunk_repo.bulk_create(
        document.id, library.id, [(0, "some content", [0.1] * new_dimension)]
    )
    db_session.commit()

    assert chunk_repo.count_for_document(document.id) == 1


def test_enable_switch_reembeds_real_library_description_embeddings(db_session, restore_embedding_dim):
    """A library's description_embedding isn't covered by the chunk_count == 0 lock that gates a
    provider switch (a library can have a description with zero documents) — this proves
    EmbeddingProviderConfigService.enable() actually nulls-then-recomputes it against a real
    libraries row, not just against mocks (see test_embedding_provider_settings_service.py's
    mocked equivalent)."""
    provider_settings_repo = EmbeddingProviderSettingsRepository(db_session)
    provider_settings_repo.upsert_config("ollama", "nomic-embed-text", None, "http://ollama:11434", 768, 800, 100)
    provider_settings_repo.set_enabled("ollama", True)
    db_session.commit()

    library_repo = LibraryRepository(db_session)
    library = library_repo.create(name="resync-test", description="a library")
    library_repo.set_description_embedding(library.id, [0.9] * 768)  # stale, from the old provider
    db_session.commit()

    embedding_provider_service = EmbeddingProviderConfigService(
        provider_settings_repo, ChunkRepository(db_session), library_repo
    )
    new_dimension = 1024
    new_description_vector = [0.5] * new_dimension
    provider = MagicMock()
    provider.embed_query.return_value = [0.1] * new_dimension
    provider.embed_documents.return_value = [new_description_vector]
    with patch(
        "app.application.embedding_provider_settings_service.EmbeddingProviderRegistry.resolve",
        return_value=provider,
    ):
        embedding_provider_service.update_config(
            "voyage", "voyage-4-lite", "test-key", None, new_dimension, 800, 100
        )
        db_session.commit()
        embedding_provider_service.enable("voyage")
    db_session.commit()

    candidates = library_repo.search_by_description_similarity(new_description_vector, top_n=10, min_similarity=0.99)
    assert [candidate.id for candidate, _similarity in candidates] == [library.id]
