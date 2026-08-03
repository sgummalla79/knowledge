from unittest.mock import MagicMock

from app.application.search_settings_service import SearchSettingsService


def test_update_passes_values_through_to_the_repository():
    repository = MagicMock()
    service = SearchSettingsService(repository)

    service.update(dense_k=30, sparse_k=15, rrf_k=40)

    repository.upsert.assert_called_once_with(dense_k=30, sparse_k=15, rrf_k=40)
