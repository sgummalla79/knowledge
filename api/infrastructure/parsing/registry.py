from api.infrastructure.parsing.html_parser import HtmlParser
from api.infrastructure.parsing.markdown_parser import MarkdownParser
from api.infrastructure.parsing.pdf_parser import PdfParser
from api.infrastructure.parsing.text_parser import TextParser

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
        return ParserRegistry.resolve_by_file_type(extension.lstrip("."))

    @staticmethod
    def resolve_by_file_type(file_type: str):
        """Keys off a document's stored, immutable `file_type` column rather than re-deriving an
        extension from `source_filename` — the filename can be renamed after upload
        (DocumentService.rename_document), but file_type never changes, so parser selection on
        retry stays correct regardless of what the document is currently named."""
        parser = _PARSERS_BY_EXTENSION.get("." + file_type)
        if parser is None:
            raise UnsupportedFileTypeError(f"No parser registered for file type '{file_type}'")
        return parser

    @staticmethod
    def supported_extensions():
        return sorted(_PARSERS_BY_EXTENSION.keys())
