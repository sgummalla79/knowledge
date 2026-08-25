from io import BytesIO
from unittest.mock import patch

import pytest
from pdfplumber.page import Page
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from api.infrastructure.parsing.pdf_parser import PdfParser


def make_pdf_bytes(pages: list[str]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    for text in pages:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _write(tmp_path, file_bytes: bytes, name: str = "upload.pdf"):
    path = tmp_path / name
    path.write_bytes(file_bytes)
    return path


def test_parse_extracts_text(tmp_path):
    path = _write(tmp_path, make_pdf_bytes(["Hello world, this is page one."]))
    assert "Hello world, this is page one." in PdfParser().parse(path)


def test_parse_joins_multiple_pages_with_newline(tmp_path):
    path = _write(tmp_path, make_pdf_bytes(["First page content.", "Second page content."]))
    text = PdfParser().parse(path)
    first_index = text.index("First page content.")
    second_index = text.index("Second page content.")
    assert first_index < second_index
    assert "\n" in text[first_index:second_index]


def test_parse_handles_page_with_no_extractable_text(tmp_path):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.showPage()  # blank page, no text drawn
    pdf.save()
    path = _write(tmp_path, buffer.getvalue())
    assert PdfParser().parse(path) == ""


def test_parse_releases_each_pages_cache_before_moving_to_the_next(tmp_path):
    """Regression test for a real production OOM: without an explicit page.close() per page,
    pdfplumber keeps every page's parsed object graph (.chars/.rects/.lines/.layout -- real Python
    objects per glyph/line/rect) cached and alive for the whole document, since the outer
    PDF.close() only releases them at the very end, after a page-dense PDF has already peaked
    memory during parsing. Verified by spying on extract_text() and checking that every
    previously-seen page's cache (its "_objects" dict entry, populated by extract_text/close()'s
    counterpart) has already been released by the time the next page starts -- i.e. at most one
    page's heavy data is ever live at once, not "close() was called N times" (which close()'s own
    idempotent, called-again-at-with-block-exit behavior makes a much weaker signal)."""
    path = _write(tmp_path, make_pdf_bytes(["page one", "page two", "page three"]))
    seen_pages = []
    original_extract_text = Page.extract_text

    def spy_extract_text(self, *args, **kwargs):
        for prior in seen_pages:
            assert "_objects" not in prior.__dict__, "an earlier page's cache is still live"
        seen_pages.append(self)
        return original_extract_text(self, *args, **kwargs)

    with patch.object(Page, "extract_text", spy_extract_text):
        PdfParser().parse(path)

    assert len(seen_pages) == 3


def test_parse_releases_a_pages_cache_even_when_its_own_extraction_raises(tmp_path):
    """The finally in PdfParser.parse() must still release a page's cache on the error path --
    otherwise a single bad page in an otherwise-fine document would leak exactly the same way the
    unfixed code always did."""
    path = _write(tmp_path, make_pdf_bytes(["page one"]))
    captured = {}

    def failing_extract_text(self, *args, **kwargs):
        captured["page"] = self
        self.chars  # populate the heavy cache, same as a real extraction would before failing
        raise RuntimeError("corrupt page")

    with patch.object(Page, "extract_text", failing_extract_text):
        with pytest.raises(RuntimeError):
            PdfParser().parse(path)

    assert "_objects" not in captured["page"].__dict__
