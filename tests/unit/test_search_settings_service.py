from unittest.mock import MagicMock

import pytest

from app.application.search_settings_service import SearchSettingsService
from app.domain.errors import ValidationError

# SUPPORTED_RERANK_MODELS_BY_PROVIDER is intentionally empty (Voyage rerank is inactive, same as
# Voyage embeddings) — these tests verify that leaving rerank off still works normally, and that
# turning it on is rejected since there's no supported provider to turn it on with.


def _service():
    return SearchSettingsService(MagicMock())


def test_update_with_rerank_disabled_does_not_validate_provider():
    # "voyage"/"rerank-2" are no longer a supported pair, but since rerank_enabled=False, that
    # should never be checked — other settings (dense_k, sparse_k, ...) must stay updatable.
    service = _service()
    service.update(
        rerank_enabled=False,
        rerank_provider="voyage",
        rerank_model="rerank-2",
        dense_k=20,
        sparse_k=20,
        rerank_candidates=20,
        rrf_k=60,
    )


def test_update_with_rerank_enabled_raises_since_no_provider_is_supported():
    service = _service()
    with pytest.raises(ValidationError) as exc_info:
        service.update(
            rerank_enabled=True,
            rerank_provider="voyage",
            rerank_model="rerank-2",
            dense_k=20,
            sparse_k=20,
            rerank_candidates=20,
            rrf_k=60,
        )
    assert exc_info.value.field == "rerank_provider"
