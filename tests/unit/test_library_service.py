from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.library_service import LibraryService
from app.domain import error_codes
from app.domain.entities import EmbeddingSettings, Library
from app.domain.errors import NotFoundError


def _library(**overrides):
    fields = dict(
        id=uuid4(), name="docs", description="a library", document_count=0, chunk_count=0,
        last_ingested_at=None, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return Library(**fields)


def _embedding_settings(**overrides):
    fields = dict(
        id=uuid4(), provider="ollama", model="nomic-embed-text", api_key=None, base_url="http://ollama:11434",
        dimensions=768, chunk_size=800, chunk_overlap=100,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return EmbeddingSettings(**fields)


def _mock_provider(vector=None, error=None):
    provider = MagicMock()
    if error is not None:
        provider.embed_query.side_effect = error
    else:
        provider.embed_query.return_value = vector
    return provider


def test_create_library_with_no_description_clears_embedding():
    repository = MagicMock()
    repository.create.return_value = _library(description=None)
    embedding_settings_repo = MagicMock()
    service = LibraryService(repository, embedding_settings_repo)

    library = service.create_library("docs", None)

    repository.set_description_embedding.assert_called_once_with(library.id, None)
    embedding_settings_repo.get.assert_not_called()


def test_create_library_with_description_but_no_active_provider_clears_embedding():
    repository = MagicMock()
    library = _library()
    repository.create.return_value = library
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = None
    service = LibraryService(repository, embedding_settings_repo)

    service.create_library("docs", "a library")

    repository.set_description_embedding.assert_called_once_with(library.id, None)


def test_create_library_with_description_and_active_provider_embeds_it():
    repository = MagicMock()
    library = _library()
    repository.create.return_value = library
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    service = LibraryService(repository, embedding_settings_repo)

    vector = [0.1] * 768
    with patch(
        "app.application.library_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(vector=vector),
    ):
        service.create_library("docs", "a library")

    repository.set_description_embedding.assert_called_once_with(library.id, vector)


def test_create_library_embed_failure_is_swallowed_and_clears_embedding():
    repository = MagicMock()
    library = _library()
    repository.create.return_value = library
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    service = LibraryService(repository, embedding_settings_repo)

    with patch(
        "app.application.library_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(error=RuntimeError("connection refused")),
    ):
        library_result = service.create_library("docs", "a library")

    assert library_result == library
    repository.set_description_embedding.assert_called_once_with(library.id, None)


def test_update_library_not_found_raises():
    repository = MagicMock()
    repository.get.return_value = None
    service = LibraryService(repository, MagicMock())

    with pytest.raises(NotFoundError) as exc_info:
        service.update_library(uuid4(), "docs", "a library")

    assert exc_info.value.code == error_codes.LIBRARY_NOT_FOUND


def test_update_library_syncs_description_embedding():
    repository = MagicMock()
    library = _library()
    repository.get.return_value = library
    repository.update.return_value = library
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    service = LibraryService(repository, embedding_settings_repo)

    vector = [0.2] * 768
    with patch(
        "app.application.library_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(vector=vector),
    ):
        service.update_library(library.id, "docs", "updated description")

    repository.set_description_embedding.assert_called_once_with(library.id, vector)
