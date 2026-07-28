import logging

import voyageai

from app.infrastructure.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            result = self._client.embed(texts, model=self._model, input_type="document")
        except Exception:
            # Broad except: voyageai's Client doesn't document a narrow exception type for this
            # codebase's usage, so this is deliberately wide, not an oversight. Breadcrumb only —
            # re-raised and logged with a full traceback at the outer job boundary.
            logger.warning(
                "Voyage embedding request failed", extra={"model": self._model, "batch_size": len(texts)}
            )
            raise
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            result = self._client.embed([text], model=self._model, input_type="query")
        except Exception:
            logger.warning("Voyage embedding request failed", extra={"model": self._model, "batch_size": 1})
            raise
        return result.embeddings[0]
