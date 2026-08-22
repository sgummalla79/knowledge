from unittest.mock import MagicMock, patch

import pytest

from api.domain.errors import IngestionCancelled
from api.infrastructure.embeddings.voyage_provider import VoyageEmbeddingProvider


def _mock_result(embeddings):
    result = MagicMock()
    result.embeddings = embeddings
    return result


def test_embed_documents_small_input_is_a_single_batch():
    provider = VoyageEmbeddingProvider(api_key="test-key", model="voyage-3")
    with patch.object(provider._client, "embed") as mock_embed:
        mock_embed.return_value = _mock_result([[0.1], [0.2]])
        result = provider.embed_documents(["a", "b"])

    assert result == [[0.1], [0.2]]
    mock_embed.assert_called_once_with(["a", "b"], model="voyage-3", input_type="document")


def test_embed_documents_splits_large_inputs_into_batches_of_128():
    # Voyage's own SDK enforces a hard 128-texts-per-request cap (embeddings_utils.py's own
    # batching helpers use the same VOYAGE_EMBED_BATCH_SIZE) — this is the real incident this
    # regression-tests: a 457-chunk document sent in one request either violates that cap or, once
    # a payment method is missing, blows straight through Voyage's reduced free-tier rate limits.
    provider = VoyageEmbeddingProvider(api_key="test-key", model="voyage-3")
    texts = [f"chunk-{i}" for i in range(300)]  # > 2x the 128-per-batch size

    def _respond(batch, model, input_type):
        return _mock_result([[0.1]] * len(batch))

    with patch.object(provider._client, "embed") as mock_embed:
        mock_embed.side_effect = _respond
        result = provider.embed_documents(texts)

    assert len(result) == 300
    assert mock_embed.call_count == 3  # 128 + 128 + 44
    batch_sizes = [len(call.args[0]) for call in mock_embed.call_args_list]
    assert batch_sizes == [128, 128, 44]
    assert all(call.kwargs["input_type"] == "document" for call in mock_embed.call_args_list)
    # Order is preserved across batch boundaries.
    all_inputs = [text for call in mock_embed.call_args_list for text in call.args[0]]
    assert all_inputs == texts


def test_embed_query_returns_single_vector():
    provider = VoyageEmbeddingProvider(api_key="test-key", model="voyage-3")
    with patch.object(provider._client, "embed") as mock_embed:
        mock_embed.return_value = _mock_result([[0.5, 0.6]])
        result = provider.embed_query("what is this?")

    assert result == [0.5, 0.6]
    mock_embed.assert_called_once_with(["what is this?"], model="voyage-3", input_type="query")


def test_embed_documents_failure_in_later_batch_propagates():
    provider = VoyageEmbeddingProvider(api_key="test-key", model="voyage-3")
    texts = [f"chunk-{i}" for i in range(150)]  # 2 batches: 128 + 22

    with patch.object(provider._client, "embed") as mock_embed:
        mock_embed.side_effect = [_mock_result([[0.1]] * 128), RuntimeError("rate limited")]
        with pytest.raises(RuntimeError):
            provider.embed_documents(texts)

    assert mock_embed.call_count == 2


def test_embed_documents_stops_before_batch_when_cancelled():
    provider = VoyageEmbeddingProvider(api_key="test-key", model="voyage-3")
    texts = [f"chunk-{i}" for i in range(150)]  # 2 batches: 128 + 22

    with patch.object(provider._client, "embed") as mock_embed:
        mock_embed.return_value = _mock_result([[0.1]] * 128)
        should_cancel = MagicMock(side_effect=[False, True])
        with pytest.raises(IngestionCancelled):
            provider.embed_documents(texts, should_cancel=should_cancel)

    assert mock_embed.call_count == 1
