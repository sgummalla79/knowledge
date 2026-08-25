from pathlib import Path

from bs4 import BeautifulSoup

from api.infrastructure.parsing.base import DocumentParser

_BOILERPLATE_TAGS = ("script", "style", "noscript")


class HtmlParser(DocumentParser):
    def parse(self, path: str | Path) -> str:
        # Small by construction (never the memory concern PDFs are -- see
        # docs/UPLOAD_STORAGE_REDESIGN.md), so a plain whole-file read is fine here.
        soup = BeautifulSoup(Path(path).read_bytes(), "html.parser")
        for tag in soup(_BOILERPLATE_TAGS):
            tag.decompose()
        lines = (line.strip() for line in soup.get_text("\n").splitlines())
        return "\n".join(line for line in lines if line)
