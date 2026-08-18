import pytest

from api.infrastructure.parsing.markdown_parser import MarkdownParser
from api.infrastructure.parsing.pdf_parser import PdfParser
from api.infrastructure.parsing.registry import ParserRegistry, UnsupportedFileTypeError
from api.infrastructure.parsing.text_parser import TextParser


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


@pytest.mark.parametrize(
    "file_type,expected_type",
    [
        ("md", MarkdownParser),
        ("txt", TextParser),
        ("pdf", PdfParser),
    ],
)
def test_resolve_by_file_type_returns_expected_parser(file_type, expected_type):
    assert isinstance(ParserRegistry.resolve_by_file_type(file_type), expected_type)


def test_resolve_by_file_type_unknown_raises():
    with pytest.raises(UnsupportedFileTypeError):
        ParserRegistry.resolve_by_file_type("docx")
