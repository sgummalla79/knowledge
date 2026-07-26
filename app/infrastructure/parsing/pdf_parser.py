from io import BytesIO

from pypdf import PdfReader

from app.infrastructure.parsing.base import DocumentParser


class PdfParser(DocumentParser):
    def parse(self, file_bytes: bytes) -> str:
        reader = PdfReader(BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
