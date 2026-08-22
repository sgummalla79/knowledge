from io import BytesIO

import pdfplumber

from api.infrastructure.parsing.base import DocumentParser


class PdfParser(DocumentParser):
    """Uses pdfplumber (font-metrics/layout-aware word reconstruction) rather than pypdf's
    glyph-gap heuristic, which regularly splits words mid-token on kerned or justified PDF text
    (e.g. "agent" -> "ag ent") and corrupts retrieval/embedding quality downstream. pypdf is still
    used in pdf_splitter.py, where only page count and a rough per-page character density feed
    split-size math — text fidelity doesn't matter there the way it does for ingested content."""

    def parse(self, file_bytes: bytes) -> str:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
