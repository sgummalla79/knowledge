from bs4 import BeautifulSoup

from api.infrastructure.parsing.base import DocumentParser

_BOILERPLATE_TAGS = ("script", "style", "noscript")


class HtmlParser(DocumentParser):
    def parse(self, file_bytes: bytes) -> str:
        soup = BeautifulSoup(file_bytes, "html.parser")
        for tag in soup(_BOILERPLATE_TAGS):
            tag.decompose()
        lines = (line.strip() for line in soup.get_text("\n").splitlines())
        return "\n".join(line for line in lines if line)
