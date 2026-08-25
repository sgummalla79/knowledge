from pathlib import Path

from api.infrastructure.parsing.base import DocumentParser


class MarkdownParser(DocumentParser):
    def parse(self, path: str | Path) -> str:
        # Small by construction (never the memory concern PDFs are -- see
        # docs/UPLOAD_STORAGE_REDESIGN.md), so a plain whole-file read is fine here.
        return Path(path).read_bytes().decode("utf-8", errors="replace")
