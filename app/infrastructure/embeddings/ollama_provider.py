import logging

import requests

from app.infrastructure.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

_EMBED_PATH = "/api/embed"
# nomic-embed-text was trained with task-instruction prefixes; omitting them measurably hurts
# retrieval quality. Mirrors VoyageEmbeddingProvider's embed_documents/embed_query split
# (input_type "document" vs "query") one level down, at the text level instead of an API parameter.
_DOCUMENT_PREFIX = "search_document: "
_QUERY_PREFIX = "search_query: "
_REQUEST_TIMEOUT_SECONDS = 60


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([_DOCUMENT_PREFIX + text for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([_QUERY_PREFIX + text])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = requests.post(
                f"{self._base_url}{_EMBED_PATH}",
                json={"model": self._model, "input": inputs},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            # A breadcrumb, not the final failure record — this gets re-raised and ultimately
            # logged with a full traceback at the outer job boundary (document_service.py), which
            # doesn't otherwise have base_url/model/batch_size context. Cross-referenced by
            # job_id, this is what actually answers "did this fail because of a timeout."
            logger.warning(
                "Ollama embedding request failed",
                extra={"base_url": self._base_url, "model": self._model, "batch_size": len(inputs)},
            )
            raise RuntimeError(f"Ollama embedding request failed: {error}") from error
        embeddings = response.json().get("embeddings")
        if not embeddings:
            logger.warning(
                "Ollama returned no embeddings",
                extra={"base_url": self._base_url, "model": self._model, "batch_size": len(inputs)},
            )
            raise RuntimeError(f"Ollama returned no embeddings for model '{self._model}'.")
        return embeddings
