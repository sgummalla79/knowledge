from unittest.mock import MagicMock, patch

import pytest
import requests

from app.infrastructure.embeddings.ollama_provider import OllamaEmbeddingProvider


def _mock_response(embeddings):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"embeddings": embeddings}
    return response


def test_embed_documents_prefixes_and_posts_input():
    provider = OllamaEmbeddingProvider(base_url="http://ollama:11434", model="nomic-embed-text")
    with patch("app.infrastructure.embeddings.ollama_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.1, 0.2], [0.3, 0.4]])
        result = provider.embed_documents(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["input"] == ["search_document: hello", "search_document: world"]
    assert kwargs["json"]["model"] == "nomic-embed-text"
    assert mock_post.call_args[0][0] == "http://ollama:11434/api/embed"


def test_embed_query_prefixes_and_returns_single_vector():
    provider = OllamaEmbeddingProvider(base_url="http://ollama:11434", model="nomic-embed-text")
    with patch("app.infrastructure.embeddings.ollama_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.5, 0.6]])
        result = provider.embed_query("what is this?")

    assert result == [0.5, 0.6]
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["input"] == ["search_query: what is this?"]


def test_base_url_trailing_slash_is_stripped():
    provider = OllamaEmbeddingProvider(base_url="http://ollama:11434/", model="nomic-embed-text")
    with patch("app.infrastructure.embeddings.ollama_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([[0.1]])
        provider.embed_query("x")

    assert mock_post.call_args[0][0] == "http://ollama:11434/api/embed"


def test_request_failure_wrapped_in_runtime_error():
    provider = OllamaEmbeddingProvider(base_url="http://ollama:11434", model="nomic-embed-text")
    with patch("app.infrastructure.embeddings.ollama_provider.requests.post") as mock_post:
        mock_post.side_effect = requests.ConnectionError("connection refused")
        with pytest.raises(RuntimeError):
            provider.embed_query("x")


def test_empty_embeddings_response_raises_runtime_error():
    provider = OllamaEmbeddingProvider(base_url="http://ollama:11434", model="nomic-embed-text")
    with patch("app.infrastructure.embeddings.ollama_provider.requests.post") as mock_post:
        mock_post.return_value = _mock_response([])
        with pytest.raises(RuntimeError):
            provider.embed_query("x")
