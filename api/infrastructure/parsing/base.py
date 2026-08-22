from abc import ABC, abstractmethod


class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes) -> str:
        """Return the plain-text content extracted from a file's raw bytes."""
