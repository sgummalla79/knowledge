from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.application.category_router_service import CategoryRouterService
from api.constants import DEFAULT_ROUTER_MIN_SIMILARITY, DEFAULT_ROUTER_TOP_N
from api.domain import error_codes
from api.domain.entities import Category, EmbeddingSettings, ScoredChunk
from api.domain.errors import ValidationError


def _embedding_settings(**overrides):
    fields = dict(
        id=uuid4(), provider="ollama", model="nomic-embed-text", api_key=None, base_url="http://ollama:11434",
        dimensions=768, chunk_size=800, chunk_overlap=100,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return EmbeddingSettings(**fields)


def _category(name="docs", **overrides):
    fields = dict(
        id=uuid4(), org_id=uuid4(), parent_id=None, name=name, slug=name, description="a category",
        created_by=None, last_modified_by=None,
        created_at=datetime.now(timezone.utc), last_modified_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return Category(**fields)


def _chunk(**overrides):
    fields = dict(id=uuid4(), document_id=uuid4(), ordinal=0, content="hello", score=0.5)
    fields.update(overrides)
    return ScoredChunk(**fields)


def _mock_provider(vector):
    provider = MagicMock()
    provider.embed_query.return_value = vector
    return provider


def _build_service(category_repo=None, embedding_settings_repo=None, retrieval_service=None):
    return CategoryRouterService(
        category_repo or MagicMock(),
        embedding_settings_repo or MagicMock(),
        retrieval_service or MagicMock(),
    )


def test_query_raises_when_no_provider_configured():
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = None
    service = _build_service(embedding_settings_repo=embedding_settings_repo)

    with pytest.raises(ValidationError) as exc_info:
        service.query(uuid4(), "hello", top_k=5)

    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED


def test_query_returns_empty_list_when_no_category_clears_threshold():
    org_id = uuid4()
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    category_repo = MagicMock()
    category_repo.search_by_description_similarity.return_value = []
    retrieval_service = MagicMock()
    service = _build_service(
        category_repo=category_repo,
        embedding_settings_repo=embedding_settings_repo,
        retrieval_service=retrieval_service,
    )

    with patch(
        "api.application.category_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 768),
    ):
        result = service.query(org_id, "hello", top_k=5)

    assert result == []
    retrieval_service.query.assert_not_called()


def test_query_single_candidate_passes_through_embedding():
    org_id = uuid4()
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()

    category = _category("docs", org_id=org_id)
    category_repo = MagicMock()
    category_repo.search_by_description_similarity.return_value = [(category, 0.9)]

    chunk = _chunk(content="alpha")
    retrieval_service = MagicMock()
    retrieval_service.query.return_value = [chunk]

    service = _build_service(
        category_repo=category_repo,
        embedding_settings_repo=embedding_settings_repo,
        retrieval_service=retrieval_service,
    )

    query_vector = [0.1] * 768
    with patch(
        "api.application.category_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(query_vector),
    ):
        result = service.query(org_id, "hello", top_k=5)

    category_repo.search_by_description_similarity.assert_called_once_with(
        org_id, query_vector, top_n=DEFAULT_ROUTER_TOP_N, min_similarity=DEFAULT_ROUTER_MIN_SIMILARITY
    )
    retrieval_service.query.assert_called_once_with(
        org_id, "hello", 5, category_id=category.id, query_embedding=query_vector
    )
    assert len(result) == 1
    assert result[0].category_id == category.id
    assert result[0].category_name == "docs"
    assert result[0].chunk.content == "alpha"


def test_query_merges_two_candidates_via_rrf_ordering():
    org_id = uuid4()
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()

    category_a = _category("a", org_id=org_id)
    category_b = _category("b", org_id=org_id)
    category_repo = MagicMock()
    category_repo.search_by_description_similarity.return_value = [(category_a, 0.9), (category_b, 0.8)]

    chunk_a1 = _chunk(content="a1")
    chunk_a2 = _chunk(content="a2")
    chunk_b1 = _chunk(content="b1")

    retrieval_service = MagicMock()
    retrieval_service.query.side_effect = [[chunk_a1, chunk_a2], [chunk_b1]]

    service = _build_service(
        category_repo=category_repo,
        embedding_settings_repo=embedding_settings_repo,
        retrieval_service=retrieval_service,
    )

    with patch(
        "api.application.category_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider([0.1] * 768),
    ):
        result = service.query(org_id, "hello", top_k=5)

    # a1 and b1 both rank 1 in their own list (tied RRF score) — stable sort preserves the order
    # candidates were retrieved in (category_a before category_b), so a1 precedes b1; a2 (rank 2)
    # comes last.
    assert [routed.chunk.content for routed in result] == ["a1", "b1", "a2"]
    assert [routed.category_name for routed in result] == ["a", "b", "a"]
