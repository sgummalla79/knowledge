import logging
from typing import Callable

import voyageai

from app.domain.errors import IngestionCancelled
from app.infrastructure.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Voyage's own hard per-request limit (their SDK's own batching helpers in embeddings_utils.py
# enforce the same number) — not a tunable of ours. Imported rather than hardcoded so it can never
# drift out of sync with whatever the installed voyageai version actually enforces. Mirrors
# OllamaEmbeddingProvider/OpenAICompatibleEmbeddingProvider's batching rationale: a single
# document's full chunk set previously went out in one request, which both violates this
# server-enforced cap for anything over 128 chunks and made a transient failure lose the whole
# document's progress instead of just one batch's.
_DOCUMENT_BATCH_SIZE = voyageai.VOYAGE_EMBED_BATCH_SIZE


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        self._client = voyageai.Client(api_key=api_key)
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
            embeddings.extend(self._embed(batch, input_type="document"))
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        try:
            result = self._client.embed(texts, model=self._model, input_type=input_type)
        except Exception:
            # Broad except: voyageai's Client doesn't document a narrow exception type for this
            # codebase's usage, so this is deliberately wide, not an oversight. Breadcrumb only —
            # re-raised and logged with a full traceback at the outer job boundary.
            logger.warning(
                "Voyage embedding request failed", extra={"model": self._model, "batch_size": len(texts)}
            )
            raise
        return result.embeddings
