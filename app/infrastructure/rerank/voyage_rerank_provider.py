import voyageai

from app.infrastructure.rerank.base import RerankProvider


class VoyageRerankProvider(RerankProvider):
    def __init__(self, api_key: str, model: str):
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        result = self._client.rerank(query, documents, model=self._model, top_k=top_k)
        return [(r.index, r.relevance_score) for r in result.results]
