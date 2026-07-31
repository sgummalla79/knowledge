from app.infrastructure.parsing.html_parser import HtmlParser
from app.infrastructure.parsing.markdown_parser import MarkdownParser
from app.infrastructure.parsing.pdf_parser import PdfParser
from app.infrastructure.parsing.text_parser import TextParser

_PARSERS_BY_EXTENSION = {
    ".md": MarkdownParser(),
    ".markdown": MarkdownParser(),
    ".txt": TextParser(),
    ".pdf": PdfParser(),
    ".html": HtmlParser(),
    ".htm": HtmlParser(),
}


class UnsupportedFileTypeError(ValueError):
    pass


class ParserRegistry:
    @staticmethod
    def resolve(filename: str):
        extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        parser = _PARSERS_BY_EXTENSION.get(extension)
        if parser is None:
            raise UnsupportedFileTypeError(
                f"No parser registered for file extension '{extension}'"
            )
        return parser

    @staticmethod
    def supported_extensions():
        return sorted(_PARSERS_BY_EXTENSION.keys())
