import pytest

from app.infrastructure.parsing.markdown_parser import MarkdownParser
from app.infrastructure.parsing.pdf_parser import PdfParser
from app.infrastructure.parsing.registry import ParserRegistry, UnsupportedFileTypeError
from app.infrastructure.parsing.text_parser import TextParser


@pytest.mark.parametrize(
    "filename,expected_type",
    [
        ("notes.md", MarkdownParser),
        ("notes.markdown", MarkdownParser),
        ("notes.txt", TextParser),
        ("notes.pdf", PdfParser),
    ],
)
def test_resolve_returns_expected_parser(filename, expected_type):
    assert isinstance(ParserRegistry.resolve(filename), expected_type)


def test_resolve_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        ParserRegistry.resolve("notes.docx")


def test_resolve_no_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        ParserRegistry.resolve("notes")


def test_supported_extensions_is_sorted():
    extensions = ParserRegistry.supported_extensions()
    assert extensions == sorted(extensions)
    assert ".md" in extensions and ".pdf" in extensions
