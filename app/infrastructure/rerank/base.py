from abc import ABC, abstractmethod


class RerankProvider(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        """Return (original_index, relevance_score) pairs, sorted by score descending."""
