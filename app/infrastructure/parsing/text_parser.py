from app.infrastructure.parsing.base import DocumentParser


class TextParser(DocumentParser):
    def parse(self, file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8", errors="replace")
