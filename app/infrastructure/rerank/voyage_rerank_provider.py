import logging

import voyageai

from app.infrastructure.rerank.base import RerankProvider

logger = logging.getLogger(__name__)


class VoyageRerankProvider(RerankProvider):
    def __init__(self, api_key: str, model: str):
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        try:
            result = self._client.rerank(query, documents, model=self._model, top_k=top_k)
        except Exception:
            # Broad except, deliberate — same reasoning as VoyageEmbeddingProvider. Breadcrumb
            # only; re-raised and logged with a full traceback at the caller's boundary.
            logger.warning(
                "Voyage rerank request failed", extra={"model": self._model, "document_count": len(documents)}
            )
            raise
        return [(r.index, r.relevance_score) for r in result.results]
