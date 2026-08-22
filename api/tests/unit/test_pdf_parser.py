from io import BytesIO

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


def test_parse_extracts_text():
    file_bytes = make_pdf_bytes(["Hello world, this is page one."])
    assert "Hello world, this is page one." in PdfParser().parse(file_bytes)


def test_parse_joins_multiple_pages_with_newline():
    file_bytes = make_pdf_bytes(["First page content.", "Second page content."])
    text = PdfParser().parse(file_bytes)
    first_index = text.index("First page content.")
    second_index = text.index("Second page content.")
    assert first_index < second_index
    assert "\n" in text[first_index:second_index]


def test_parse_handles_page_with_no_extractable_text():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.showPage()  # blank page, no text drawn
    pdf.save()
    assert PdfParser().parse(buffer.getvalue()) == ""
