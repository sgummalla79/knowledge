import logging

import requests

from app.infrastructure.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

_EMBED_PATH = "/embeddings"
_REQUEST_TIMEOUT_SECONDS = 120
# Mirrors OllamaEmbeddingProvider's rationale: bound each request's duration regardless of total
# document size, so a transient failure only loses one batch's progress.
_DOCUMENT_BATCH_SIZE = 100


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Speaks the OpenAI /embeddings REST shape — covers OpenAI itself, Azure OpenAI, and any
    self-hosted/proxy server (vLLM, text-embeddings-inference, LiteLLM) that mirrors it, without
    a bespoke class per vendor."""

    def __init__(self, base_url: str, api_key: str | None, model: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        batches = [
            texts[start : start + _DOCUMENT_BATCH_SIZE]
            for start in range(0, len(texts), _DOCUMENT_BATCH_SIZE)
        ]
        for batch_number, batch in enumerate(batches, start=1):
            logger.debug(
                "Embedding batch",
                extra={
                    "model": self._model,
                    "batch_size": len(batch),
                    "batch_number": batch_number,
                    "total_batches": len(batches),
                },
            )
            embeddings.extend(self._embed(batch))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            response = requests.post(
                f"{self._base_url}{_EMBED_PATH}",
                json={"model": self._model, "input": inputs},
                headers=headers,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            # Breadcrumb only — re-raised and logged with a full traceback at the outer job
            # boundary (document_service.py), which doesn't otherwise have base_url/model context.
            logger.warning(
                "OpenAI-compatible embedding request failed",
                extra={"base_url": self._base_url, "model": self._model, "batch_size": len(inputs)},
            )
            raise RuntimeError(f"OpenAI-compatible embedding request failed: {error}") from error
        data = response.json().get("data")
        if not data:
            logger.warning(
                "OpenAI-compatible endpoint returned no embeddings",
                extra={"base_url": self._base_url, "model": self._model, "batch_size": len(inputs)},
            )
            raise RuntimeError(f"OpenAI-compatible endpoint returned no embeddings for model '{self._model}'.")
        return [item["embedding"] for item in sorted(data, key=lambda item: item.get("index", 0))]
