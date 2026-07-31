from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, for storage."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Return the embedding vector for a single query string."""


@runtime_checkable
class SupportsModelListing(Protocol):
    """Optional capability, not part of EmbeddingProvider itself — a provider whose backend has
    no model-listing API (e.g. Voyage; confirmed no such endpoint exists in their SDK) simply
    doesn't implement this method, and callers that only embed are never forced to depend on it
    (Interface Segregation). Checked structurally via isinstance()/issubclass(), no explicit
    inheritance required."""

    def list_models(self) -> list[str]:
        """Return the model names currently available at this provider's endpoint, using
        whatever credentials/base_url the instance was constructed with."""
