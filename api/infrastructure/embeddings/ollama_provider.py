import logging
from typing import Callable

import requests

from api.domain.errors import IngestionCancelled
from api.infrastructure.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

_EMBED_PATH = "/api/embed"
_TAGS_PATH = "/api/tags"
_LIST_MODELS_TIMEOUT_SECONDS = 10
# nomic-embed-text was trained with task-instruction prefixes; omitting them measurably hurts
# retrieval quality. Mirrors VoyageEmbeddingProvider's embed_documents/embed_query split
# (input_type "document" vs "query") one level down, at the text level instead of an API parameter.
_DOCUMENT_PREFIX = "search_document: "
_QUERY_PREFIX = "search_query: "
_REQUEST_TIMEOUT_SECONDS = 120
# A document's full chunk set was originally sent to Ollama in one request — fine for small
# documents, but CPU-only local inference of several hundred chunks in a single call routinely
# exceeded even a generous timeout (a 457-chunk PDF timed out at 60s in practice). Splitting into
# fixed-size batches bounds each request's duration regardless of total document size, and a
# transient failure only loses one batch's progress instead of the whole document.
_DOCUMENT_BATCH_SIZE = 32


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def embed_documents(
        self, texts: list[str], should_cancel: Callable[[], bool] | None = None
    ) -> list[list[float]]:
        embeddings: list[list[float]] = []
        batches = [
            texts[start : start + _DOCUMENT_BATCH_SIZE]
            for start in range(0, len(texts), _DOCUMENT_BATCH_SIZE)
        ]
        for batch_number, batch in enumerate(batches, start=1):
            if should_cancel and should_cancel():
                raise IngestionCancelled("Cancelled by user.")
            logger.debug(
                "Embedding batch",
                extra={
                    "model": self._model,
                    "batch_size": len(batch),
                    "batch_number": batch_number,
                    "total_batches": len(batches),
                },
            )
            embeddings.extend(self._embed([_DOCUMENT_PREFIX + text for text in batch]))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self._embed([_QUERY_PREFIX + text])[0]

    def list_models(self) -> list[str]:
        """Ollama's real model-list endpoint — distinct from /api/embed, and lists whatever the
        user has locally pulled, not a fixed catalog like a hosted provider's /models."""
        try:
            response = requests.get(f"{self._base_url}{_TAGS_PATH}", timeout=_LIST_MODELS_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Ollama model listing request failed", extra={"base_url": self._base_url})
            raise RuntimeError(f"Ollama model listing request failed: {error}") from error
        return [item["name"] for item in response.json().get("models", []) if "name" in item]

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
