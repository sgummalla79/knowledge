from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.application.retrieval_service import RetrievalService
from app.domain.entities import Library, SearchSettings

# Full embed-and-retrieve behavior (dense+sparse+RRF against a real DB) is covered by
# tests/integration/test_retrieval_service.py. These unit tests only cover the optional
# query_embedding/search_settings pre-supplied-inputs path LibraryRouterService relies on to avoid
# redundant embed calls / settings lookups when fanning one query out across several libraries.


def _library(**overrides):
    fields = dict(
        id=uuid4(), name="docs", description=None, document_count=0, chunk_count=0,
        last_ingested_at=None, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return Library(**fields)


def _build_service():
    library_repo = MagicMock()
    chunk_repo = MagicMock()
    chunk_repo.similarity_search.return_value = []
    chunk_repo.sparse_search.return_value = []
    embedding_settings_repo = MagicMock()
    search_settings_repo = MagicMock()
    service = RetrievalService(library_repo, chunk_repo, embedding_settings_repo, search_settings_repo)
    return service, library_repo, chunk_repo, embedding_settings_repo, search_settings_repo


def test_pre_supplied_query_embedding_and_search_settings_skip_repo_lookups():
    service, library_repo, chunk_repo, embedding_settings_repo, search_settings_repo = _build_service()
    library = _library()
    library_repo.get.return_value = library

    query_embedding = [0.1] * 768
    search_settings = SearchSettings(dense_k=5, sparse_k=5, rrf_k=60, updated_at=None)

    with patch("app.application.retrieval_service.EmbeddingProviderRegistry.resolve") as mock_resolve:
        service.query(
            library.id, "hello", 5, query_embedding=query_embedding, search_settings=search_settings
        )
        mock_resolve.assert_not_called()

    embedding_settings_repo.get.assert_not_called()
    search_settings_repo.get.assert_not_called()
    chunk_repo.similarity_search.assert_called_once_with(library.id, query_embedding, search_settings.dense_k)
    chunk_repo.sparse_search.assert_called_once_with(library.id, "hello", search_settings.sparse_k)


def test_without_pre_supplied_inputs_falls_back_to_repo_lookups():
    service, library_repo, chunk_repo, embedding_settings_repo, search_settings_repo = _build_service()
    library = _library()
    library_repo.get.return_value = library

    from app.domain.entities import EmbeddingSettings

    embedding_settings = EmbeddingSettings(
        id=uuid4(), provider="ollama", model="nomic-embed-text", api_key=None, base_url="http://ollama:11434",
        dimensions=768, chunk_size=800, chunk_overlap=100,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    embedding_settings_repo.get.return_value = embedding_settings
    search_settings_repo.get.return_value = SearchSettings(dense_k=20, sparse_k=20, rrf_k=60, updated_at=None)

    provider = MagicMock()
    provider.embed_query.return_value = [0.2] * 768
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve", return_value=provider
    ) as mock_resolve:
        service.query(library.id, "hello", 5)
        mock_resolve.assert_called_once_with(
            embedding_settings.provider, embedding_settings.model, embedding_settings.api_key, embedding_settings.base_url
        )

    embedding_settings_repo.get.assert_called_once()
    search_settings_repo.get.assert_called_once()
