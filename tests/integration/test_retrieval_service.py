from unittest.mock import MagicMock, patch

import pytest

from app.application.retrieval_service import RetrievalService
from app.constants import EMBEDDING_DIM
from app.domain import error_codes
from app.domain.errors import NotFoundError, ValidationError
from app.infrastructure.orm import Document
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.library_repository import LibraryRepository
from app.infrastructure.repositories.search_settings_repository import SearchSettingsRepository


def _fake_provider(query_vector):
    provider = MagicMock()
    provider.embed_query.return_value = query_vector
    return provider


def _make_library(library_repo, **overrides):
    fields = dict(name="retrieval-test", description=None)
    fields.update(overrides)
    return library_repo.create(**fields)


def _make_document(db_session, library_id):
    document = Document(
        library_id=library_id,
        source_filename="notes.md",
        file_type="md",
        content_hash="abc",
        status="completed",
    )
    db_session.add(document)
    db_session.flush()
    return document


def _make_service(db_session):
    return RetrievalService(
        LibraryRepository(db_session),
        ChunkRepository(db_session),
        EmbeddingSettingsRepository(db_session),
        SearchSettingsRepository(db_session),
    )


def test_query_returns_nearest_chunks_ranked_by_hybrid_fusion(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    embedding_settings_repo = EmbeddingSettingsRepository(db_session)
    library = _make_library(library_repo)
    embedding_settings_repo.upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    near = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    far = [0.0] * (EMBEDDING_DIM - 1) + [1.0]

    document = _make_document(db_session, library.id)
    chunk_repo.bulk_create(
        document.id,
        library.id,
        [(0, "closest chunk", near), (1, "farthest chunk", far)],
    )
    db_session.commit()

    service = _make_service(db_session)
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(near),
    ):
        results = service.query(library.id, "find the closest chunk", top_k=2)

    # Both dense (embedding distance) and sparse (keyword overlap on "closest"/"chunk") agree here,
    # so fusion doesn't change the obvious ordering — this is the "fusion didn't regress an
    # obvious match" sanity check called out in the plan's verification steps.
    assert [chunk.content for chunk in results] == ["closest chunk", "farthest chunk"]


def test_hybrid_fusion_promotes_sparse_match_over_pure_dense_order(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    embedding_settings_repo = EmbeddingSettingsRepository(db_session)
    library = _make_library(library_repo, name="hybrid-fusion-test")
    embedding_settings_repo.upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    closest = [1.0] + [0.0] * (EMBEDDING_DIM - 1)  # identical to query — dense rank 1
    middle = [0.7071] * 2 + [0.0] * (EMBEDDING_DIM - 2)  # dense rank 2
    farthest = [0.0] * (EMBEDDING_DIM - 1) + [1.0]  # orthogonal to query — dense rank 3

    document = _make_document(db_session, library.id)
    chunk_repo.bulk_create(
        document.id,
        library.id,
        [
            (0, "generic filler text about nothing in particular", closest),
            (1, "more generic filler with no special terms", middle),
            (2, "zephyrpineapple is the unique marker phrase here", farthest),
        ],
    )
    db_session.commit()

    service = _make_service(db_session)
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query(library.id, "zephyrpineapple", top_k=3)

    # Dense-only would rank this chunk last (it's the farthest embedding) — hybrid fusion
    # promotes it to first because it's the only chunk that actually matches the query keyword.
    assert results[0].content == "zephyrpineapple is the unique marker phrase here"


def test_rerank_disabled_never_calls_rerank_provider(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    embedding_settings_repo = EmbeddingSettingsRepository(db_session)
    library = _make_library(library_repo, name="rerank-disabled-test")
    embedding_settings_repo.upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    near = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    document = _make_document(db_session, library.id)
    chunk_repo.bulk_create(document.id, library.id, [(0, "only chunk", near)])
    db_session.commit()

    service = _make_service(db_session)
    with (
        patch(
            "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
            return_value=_fake_provider(near),
        ),
        patch("app.application.retrieval_service.RerankProviderRegistry.resolve") as resolve_rerank,
    ):
        service.query(library.id, "only chunk", top_k=1)

    resolve_rerank.assert_not_called()


def test_rerank_enabled_reorders_using_rerank_scores(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    embedding_settings_repo = EmbeddingSettingsRepository(db_session)
    search_settings_repo = SearchSettingsRepository(db_session)
    library = _make_library(library_repo, name="rerank-enabled-test")
    embedding_settings_repo.upsert(
        "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    search_settings_repo.upsert(
        rerank_enabled=True,
        rerank_provider="voyage",
        rerank_model="rerank-2",
        dense_k=20,
        sparse_k=20,
        rerank_candidates=20,
        rrf_k=60,
    )
    db_session.commit()

    near = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    far = [0.0] * (EMBEDDING_DIM - 1) + [1.0]
    document = _make_document(db_session, library.id)
    chunk_repo.bulk_create(
        document.id,
        library.id,
        [(0, "fused first chunk", near), (1, "fused second chunk", far)],
    )
    db_session.commit()

    fake_rerank_provider = MagicMock()
    # Invert the fused order: index 1 ("fused second chunk") scores highest.
    fake_rerank_provider.rerank.return_value = [(1, 0.99), (0, 0.5)]

    service = _make_service(db_session)
    with (
        patch(
            "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
            return_value=_fake_provider(near),
        ),
        patch(
            "app.application.retrieval_service.RerankProviderRegistry.resolve",
            return_value=fake_rerank_provider,
        ),
    ):
        results = service.query(library.id, "find the fused chunk", top_k=2)

    fake_rerank_provider.rerank.assert_called_once()
    assert [chunk.content for chunk in results] == ["fused second chunk", "fused first chunk"]
    assert results[0].score == 0.99


def test_query_missing_library_raises_not_found(db_session):
    service = _make_service(db_session)

    with pytest.raises(NotFoundError):
        service.query("00000000-0000-0000-0000-000000000000", "hello", top_k=5)


def test_query_without_configured_embeddings_raises(db_session):
    library_repo = LibraryRepository(db_session)
    library = _make_library(library_repo, name="retrieval-unconfigured-test")
    db_session.commit()

    service = _make_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.query(library.id, "hello", top_k=5)
    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED
