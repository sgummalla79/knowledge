from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.library_router_service import LibraryRouterService
from app.domain import error_codes
from app.domain.entities import EmbeddingSettings, Library, RouterSettings, ScoredChunk, SearchSettings
from app.domain.errors import ValidationError


def _embedding_settings(**overrides):
    fields = dict(
        id=uuid4(), provider="ollama", model="nomic-embed-text", api_key=None, base_url="http://ollama:11434",
        dimensions=768, chunk_size=800, chunk_overlap=100,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return EmbeddingSettings(**fields)


def _library(name="docs", **overrides):
    fields = dict(
        id=uuid4(), name=name, description="a library", document_count=1, chunk_count=1,
        last_ingested_at=None, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return Library(**fields)


def _chunk(**overrides):
    fields = dict(id=uuid4(), document_id=uuid4(), chunk_index=0, content="hello", score=0.5)
    fields.update(overrides)
    return ScoredChunk(**fields)


def _mock_provider(vector):
    provider = MagicMock()
    provider.embed_query.return_value = vector
    return provider


def _build_service(library_repo=None, embedding_settings_repo=None, router_settings_repo=None,
                    search_settings_repo=None, retrieval_service=None):
    return LibraryRouterService(
        library_repo or MagicMock(),
        embedding_settings_repo or MagicMock(),
        router_settings_repo or MagicMock(),
        search_settings_repo or MagicMock(),
        retrieval_service or MagicMock(),
    )


def test_query_raises_when_no_provider_configured():
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = None
    service = _build_service(embedding_settings_repo=embedding_settings_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.query("hello", top_k=5)

    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED


def test_query_returns_empty_list_when_no_library_clears_threshold():
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    library_repo = MagicMock()
    library_repo.search_by_description_similarity.return_value = []
    retrieval_service = MagicMock()
    service = _build_service(
        library_repo=library_repo, embedding_settings_repo=embedding_settings_repo, retrieval_service=retrieval_service
    )

    with patch(
        "app.application.library_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 768),
    ):
        result = service.query("hello", top_k=5)

    assert result == []
    retrieval_service.query.assert_not_called()


def test_query_single_candidate_passes_through_embedding_and_settings():
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    router_settings_repo = MagicMock()
    router_settings_repo.get.return_value = RouterSettings(top_n=3, min_similarity=0.5, updated_at=None)
    search_settings_repo = MagicMock()
    search_settings = SearchSettings(dense_k=20, sparse_k=20, rrf_k=60, updated_at=None)
    search_settings_repo.get.return_value = search_settings

    library = _library("docs")
    library_repo = MagicMock()
    library_repo.search_by_description_similarity.return_value = [(library, 0.9)]

    chunk = _chunk(content="alpha")
    retrieval_service = MagicMock()
    retrieval_service.query.return_value = [chunk]

    service = _build_service(
        library_repo=library_repo,
        embedding_settings_repo=embedding_settings_repo,
        router_settings_repo=router_settings_repo,
        search_settings_repo=search_settings_repo,
        retrieval_service=retrieval_service,
    )

    query_vector = [0.1] * 768
    with patch(
        "app.application.library_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(query_vector),
    ):
        result = service.query("hello", top_k=5)

    library_repo.search_by_description_similarity.assert_called_once_with(query_vector, top_n=3, min_similarity=0.5)
    retrieval_service.query.assert_called_once_with(
        library.id, "hello", 5, query_embedding=query_vector, search_settings=search_settings
    )
    assert len(result) == 1
    assert result[0].library_id == library.id
    assert result[0].library_name == "docs"
    assert result[0].chunk.content == "alpha"


def test_query_merges_two_candidates_via_rrf_ordering():
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    router_settings_repo = MagicMock()
    router_settings_repo.get.return_value = RouterSettings(top_n=2, min_similarity=0.5, updated_at=None)
    search_settings_repo = MagicMock()
    search_settings_repo.get.return_value = SearchSettings(dense_k=20, sparse_k=20, rrf_k=60, updated_at=None)

    library_a = _library("a")
    library_b = _library("b")
    library_repo = MagicMock()
    library_repo.search_by_description_similarity.return_value = [(library_a, 0.9), (library_b, 0.8)]

    chunk_a1 = _chunk(content="a1")
    chunk_a2 = _chunk(content="a2")
    chunk_b1 = _chunk(content="b1")

    retrieval_service = MagicMock()
    retrieval_service.query.side_effect = [[chunk_a1, chunk_a2], [chunk_b1]]

    service = _build_service(
        library_repo=library_repo,
        embedding_settings_repo=embedding_settings_repo,
        router_settings_repo=router_settings_repo,
        search_settings_repo=search_settings_repo,
        retrieval_service=retrieval_service,
    )

    with patch(
        "app.application.library_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 768),
    ):
        result = service.query("hello", top_k=5)

    # a1 and b1 both rank 1 in their own list (tied RRF score) — stable sort preserves the order
    # candidates were retrieved in (library_a before library_b), so a1 precedes b1; a2 (rank 2)
    # comes last.
    assert [routed.chunk.content for routed in result] == ["a1", "b1", "a2"]
    assert [routed.library_name for routed in result] == ["a", "b", "a"]
