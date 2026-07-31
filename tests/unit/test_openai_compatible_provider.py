from unittest.mock import MagicMock, patch

import pytest
import requests

from app.domain.errors import IngestionCancelled
from app.infrastructure.embeddings.openai_compatible_provider import OpenAICompatibleEmbeddingProvider


def _mock_response(vectors):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": [{"embedding": vector, "index": index} for index, vector in enumerate(vectors)]
    }
    return response


def test_embed_documents_posts_input_and_returns_vectors_in_order():
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://api.openai.com/v1", api_key="test-key", model="text-embedding-3-small"
    )
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.1, 0.2], [0.3, 0.4]])
        result = provider.embed_documents(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.openai.com/v1/embeddings"
    assert kwargs["json"] == {"model": "text-embedding-3-small", "input": ["hello", "world"]}
    assert kwargs["headers"] == {"Authorization": "Bearer test-key"}


def test_embed_query_returns_single_vector():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.5, 0.6]])
        result = provider.embed_query("what is this?")

    assert result == [0.5, 0.6]


def test_no_api_key_sends_no_authorization_header():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.1]])
        provider.embed_query("x")

    assert mock_post.call_args.kwargs["headers"] == {}


def test_base_url_trailing_slash_is_stripped():
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://api.openai.com/v1/", api_key="key", model="text-embedding-3-small"
    )
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.1]])
        provider.embed_query("x")

    assert mock_post.call_args[0][0] == "https://api.openai.com/v1/embeddings"


def test_response_data_reordered_by_index():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": [
            {"embedding": [0.9, 0.9], "index": 1},
            {"embedding": [0.1, 0.1], "index": 0},
        ]
    }
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = response
        result = provider.embed_documents(["first", "second"])

    assert result == [[0.1, 0.1], [0.9, 0.9]]


def test_request_failure_wrapped_in_runtime_error():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.side_effect = requests.ConnectionError("connection refused")
        with pytest.raises(RuntimeError):
            provider.embed_query("x")


def test_empty_data_response_raises_runtime_error():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([])
        with pytest.raises(RuntimeError):
            provider.embed_query("x")


def test_embed_documents_splits_large_inputs_into_multiple_batched_requests():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    texts = [f"chunk-{i}" for i in range(220)]  # > 2x the 100-per-batch size

    def _respond(url, json, headers, timeout):
        return _mock_response([[0.1]] * len(json["input"]))

    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.side_effect = _respond
        result = provider.embed_documents(texts)

    assert len(result) == 220
    assert mock_post.call_count == 3  # 100 + 100 + 20
    batch_sizes = [len(call.kwargs["json"]["input"]) for call in mock_post.call_args_list]
    assert batch_sizes == [100, 100, 20]


def test_embed_documents_stops_before_batch_when_cancelled():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="local-model")
    texts = [f"chunk-{i}" for i in range(220)]  # > 2x the 100-per-batch size

    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.1]] * 100)
        should_cancel = MagicMock(side_effect=[False, True])
        with pytest.raises(IngestionCancelled):
            provider.embed_documents(texts, should_cancel=should_cancel)

    assert mock_post.call_count == 1


def test_list_models_returns_model_ids():
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://api.openai.com/v1", api_key="test-key", model="unused"
    )
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "data": [{"id": "text-embedding-3-small"}, {"id": "text-embedding-3-large"}]
    }
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.get") as mock_get:
        mock_get.return_value = response
        result = provider.list_models()

    assert result == ["text-embedding-3-small", "text-embedding-3-large"]
    args, kwargs = mock_get.call_args
    assert args[0] == "https://api.openai.com/v1/models"
    assert kwargs["headers"] == {"Authorization": "Bearer test-key"}


def test_list_models_without_api_key_sends_no_authorization_header():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="unused")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": []}
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.get") as mock_get:
        mock_get.return_value = response
        provider.list_models()

    assert mock_get.call_args.kwargs["headers"] == {}


def test_list_models_request_failure_wrapped_in_runtime_error():
    provider = OpenAICompatibleEmbeddingProvider(base_url="http://localhost:8000", api_key=None, model="unused")
    with patch("app.infrastructure.embeddings.openai_compatible_provider.requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("connection refused")
        with pytest.raises(RuntimeError):
            provider.list_models()
