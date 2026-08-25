from abc import ABC, abstractmethod
from pathlib import Path


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, path: str | Path) -> str:
        """Return the plain-text content extracted from the file at `path`."""
