from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.application.retrieval_service import RetrievalService
from api.constants import DEFAULT_DENSE_K, DEFAULT_SPARSE_K

# Full embed-and-retrieve behavior (dense+sparse+RRF against a real DB) is covered by
# tests/integration/test_retrieval_service.py. This unit test only covers the optional
# query_embedding pre-supplied-input path CategoryRouterService relies on to avoid a redundant
# embed call when fanning one query out across several categories, plus category_id scoping.


def _build_service():
    chunk_repo = MagicMock()
    chunk_repo.similarity_search.return_value = []
    chunk_repo.sparse_search.return_value = []
    embedding_settings_repo = MagicMock()
    service = RetrievalService(chunk_repo, embedding_settings_repo)
    return service, chunk_repo, embedding_settings_repo


def test_pre_supplied_query_embedding_skips_embedding_settings_lookup():
    service, chunk_repo, embedding_settings_repo = _build_service()
    org_id = uuid4()
    query_embedding = [0.1] * 768

    with patch("api.application.retrieval_service.EmbeddingProviderRegistry.resolve") as mock_resolve:
        service.query(org_id, "hello", 5, query_embedding=query_embedding)
        mock_resolve.assert_not_called()

    embedding_settings_repo.get.assert_not_called()
    chunk_repo.similarity_search.assert_called_once_with(org_id, query_embedding, DEFAULT_DENSE_K, None)
    chunk_repo.sparse_search.assert_called_once_with(org_id, "hello", DEFAULT_SPARSE_K, None)


def test_category_id_narrows_both_searches():
    service, chunk_repo, embedding_settings_repo = _build_service()
    org_id = uuid4()
    category_id = uuid4()
    query_embedding = [0.1] * 768

    service.query(org_id, "hello", 5, category_id=category_id, query_embedding=query_embedding)

    chunk_repo.similarity_search.assert_called_once_with(org_id, query_embedding, DEFAULT_DENSE_K, category_id)
    chunk_repo.sparse_search.assert_called_once_with(org_id, "hello", DEFAULT_SPARSE_K, category_id)


def test_without_pre_supplied_embedding_falls_back_to_provider():
    service, chunk_repo, embedding_settings_repo = _build_service()
    org_id = uuid4()

    embedding_settings = MagicMock(
        provider="ollama", model="nomic-embed-text", api_key=None, base_url="http://ollama:11434"
    )
    embedding_settings_repo.get.return_value = embedding_settings

    provider = MagicMock()
    provider.embed_query.return_value = [0.2] * 768
    with patch(
        "api.application.retrieval_service.EmbeddingProviderRegistry.resolve", return_value=provider
    ) as mock_resolve:
        service.query(org_id, "hello", 5)
        mock_resolve.assert_called_once_with(
            embedding_settings.provider, embedding_settings.model, embedding_settings.api_key, embedding_settings.base_url
        )

    embedding_settings_repo.get.assert_called_once_with(org_id)
