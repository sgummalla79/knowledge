from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.application.category_service import CategoryService
from api.domain import error_codes
from api.domain.entities import Category, EmbeddingSettings
from api.domain.errors import NotFoundError


def _category(**overrides):
    fields = dict(
        id=uuid4(), org_id=uuid4(), parent_id=None, name="docs", slug="docs", description="a category",
        created_by=None, last_modified_by=None,
        created_at=datetime.now(timezone.utc), last_modified_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return Category(**fields)


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


def test_create_category_with_no_description_clears_embedding():
    org_id = uuid4()
    repository = MagicMock()
    repository.create.return_value = _category(org_id=org_id, description=None)
    embedding_settings_repo = MagicMock()
    service = CategoryService(repository, embedding_settings_repo)

    category = service.create_category(org_id, "docs", None)

    repository.create.assert_called_once_with(org_id, name="docs", slug="docs", description=None, parent_id=None)
    repository.set_description_embedding.assert_called_once_with(category.id, None)
    embedding_settings_repo.get.assert_not_called()


def test_create_category_with_description_but_no_active_provider_clears_embedding():
    org_id = uuid4()
    repository = MagicMock()
    category = _category(org_id=org_id)
    repository.create.return_value = category
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = None
    service = CategoryService(repository, embedding_settings_repo)

    service.create_category(org_id, "docs", "a category")

    repository.set_description_embedding.assert_called_once_with(category.id, None)


def test_create_category_with_description_and_active_provider_embeds_it():
    org_id = uuid4()
    repository = MagicMock()
    category = _category(org_id=org_id)
    repository.create.return_value = category
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    service = CategoryService(repository, embedding_settings_repo)

    vector = [0.1] * 768
    with patch(
        "api.application.category_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(vector=vector),
    ):
        service.create_category(org_id, "docs", "a category")

    embedding_settings_repo.get.assert_called_once_with(org_id)
    repository.set_description_embedding.assert_called_once_with(category.id, vector)


def test_create_category_embed_failure_is_swallowed_and_clears_embedding():
    org_id = uuid4()
    repository = MagicMock()
    category = _category(org_id=org_id)
    repository.create.return_value = category
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    service = CategoryService(repository, embedding_settings_repo)

    with patch(
        "api.application.category_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(error=RuntimeError("connection refused")),
    ):
        result = service.create_category(org_id, "docs", "a category")

    assert result == category
    repository.set_description_embedding.assert_called_once_with(category.id, None)


def test_create_category_derives_slug_from_name():
    org_id = uuid4()
    repository = MagicMock()
    repository.create.return_value = _category(org_id=org_id)
    service = CategoryService(repository, MagicMock())

    service.create_category(org_id, "Product Docs!", None)

    repository.create.assert_called_once_with(
        org_id, name="Product Docs!", slug="product-docs", description=None, parent_id=None
    )


def test_get_category_missing_raises_not_found():
    repository = MagicMock()
    repository.get.return_value = None
    service = CategoryService(repository, MagicMock())

    with pytest.raises(NotFoundError) as exc_info:
        service.get_category(uuid4(), uuid4())

    assert exc_info.value.code == error_codes.CATEGORY_NOT_FOUND


def test_get_category_belonging_to_another_org_raises_not_found():
    repository = MagicMock()
    repository.get.return_value = _category(org_id=uuid4())
    service = CategoryService(repository, MagicMock())

    with pytest.raises(NotFoundError) as exc_info:
        service.get_category(uuid4(), uuid4())

    assert exc_info.value.code == error_codes.CATEGORY_NOT_FOUND


def test_update_category_not_found_raises():
    repository = MagicMock()
    repository.get.return_value = None
    service = CategoryService(repository, MagicMock())

    with pytest.raises(NotFoundError) as exc_info:
        service.update_category(uuid4(), uuid4(), "docs", "a category")

    assert exc_info.value.code == error_codes.CATEGORY_NOT_FOUND


def test_update_category_syncs_description_embedding():
    org_id = uuid4()
    repository = MagicMock()
    category = _category(org_id=org_id)
    repository.get.return_value = category
    repository.update.return_value = category
    embedding_settings_repo = MagicMock()
    embedding_settings_repo.get.return_value = _embedding_settings()
    service = CategoryService(repository, embedding_settings_repo)

    vector = [0.2] * 768
    with patch(
        "api.application.category_service.EmbeddingProviderRegistry.resolve",
        return_value=_mock_provider(vector=vector),
    ):
        service.update_category(org_id, category.id, "docs", "updated description")

    repository.set_description_embedding.assert_called_once_with(category.id, vector)


def test_delete_category_not_found_raises():
    repository = MagicMock()
    repository.get.return_value = None
    service = CategoryService(repository, MagicMock())

    with pytest.raises(NotFoundError) as exc_info:
        service.delete_category(uuid4(), uuid4())

    assert exc_info.value.code == error_codes.CATEGORY_NOT_FOUND
    repository.delete.assert_not_called()


def test_delete_category_deletes_when_found():
    org_id = uuid4()
    category = _category(org_id=org_id)
    repository = MagicMock()
    repository.get.return_value = category
    service = CategoryService(repository, MagicMock())

    service.delete_category(org_id, category.id)

    repository.delete.assert_called_once_with(category.id)


def test_list_categories_delegates_to_repository():
    org_id = uuid4()
    categories = [_category(org_id=org_id)]
    repository = MagicMock()
    repository.list_by_org.return_value = categories
    service = CategoryService(repository, MagicMock())

    result = service.list_categories(org_id)

    assert result == categories
    repository.list_by_org.assert_called_once_with(org_id)
