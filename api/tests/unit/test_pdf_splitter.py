from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from api.domain.errors import ValidationError
from api.infrastructure.parsing.pdf_splitter import PdfSplitter, plan_split


def make_pdf_bytes(pages: list[str]) -> bytes:
    """A real, parseable multi-page PDF with distinct extractable text per page — used to verify
    PdfSplitter's page-range slicing against pypdf itself, not just its own internal bookkeeping."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    for text in pages:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _page_texts(file_bytes: bytes) -> list[str]:
    reader = PdfReader(BytesIO(file_bytes))
    return [(page.extract_text() or "").strip() for page in reader.pages]


# --- plan_split: pure arithmetic ---------------------------------------------------------------


def test_plan_split_basic_case():
    plan = plan_split(
        total_pages=100,
        total_bytes=10_000_000,
        avg_chars_per_page=2500,
        chunk_size=800,
        chunk_overlap=100,
        target_part_bytes=1_000_000,
        max_parts=20,
    )
    # avg_bytes_per_page = 100_000 -> pages_per_part = 1_000_000 // 100_000 = 10
    assert plan.pages_per_part == 10
    assert plan.total_parts == 10
    # target_overlap_chars = 3 * (800+100) = 2700 -> ceil(2700/2500) = 2, within [1, 5]
    assert plan.overlap_pages == 2


def test_plan_split_clamps_overlap_to_min_for_dense_pages():
    plan = plan_split(
        total_pages=50,
        total_bytes=5_000_000,
        avg_chars_per_page=50_000,  # very dense page
        chunk_size=800,
        chunk_overlap=100,
        target_part_bytes=1_000_000,
        max_parts=20,
    )
    assert plan.overlap_pages == 1


def test_plan_split_clamps_overlap_to_max_for_near_zero_text_pages():
    plan = plan_split(
        total_pages=50,
        total_bytes=5_000_000,
        avg_chars_per_page=0,  # scanned/image-only pages, no extractable text
        chunk_size=800,
        chunk_overlap=100,
        target_part_bytes=1_000_000,
        max_parts=20,
    )
    assert plan.overlap_pages == 5


def test_plan_split_bumps_pages_per_part_above_overlap():
    # target_part_bytes tiny relative to page size -> pages_per_part would compute to 0/1, which
    # must never end up <= overlap_pages (degenerate/negative-size core segment).
    plan = plan_split(
        total_pages=100,
        total_bytes=100_000_000,
        avg_chars_per_page=100,  # sparse text -> large overlap_pages
        chunk_size=800,
        chunk_overlap=100,
        target_part_bytes=1_000,
        max_parts=50,
    )
    assert plan.pages_per_part > plan.overlap_pages


def test_plan_split_raises_when_max_parts_exceeded():
    with pytest.raises(ValidationError):
        plan_split(
            total_pages=1000,
            total_bytes=100_000_000,
            avg_chars_per_page=2500,
            chunk_size=800,
            chunk_overlap=100,
            target_part_bytes=1_000_000,
            max_parts=5,
        )


# --- PdfSplitter: pypdf-backed behavior ---------------------------------------------------------


def test_split_below_threshold_returns_original_bytes_unchanged():
    splitter = PdfSplitter(threshold_bytes=10_000_000)
    file_bytes = make_pdf_bytes(["only page"])
    assert splitter.split(file_bytes, chunk_size=800, chunk_overlap=100) == [file_bytes]


def test_should_split_reflects_threshold():
    splitter = PdfSplitter(threshold_bytes=100)
    small = make_pdf_bytes(["short"])
    assert not splitter.should_split(small[:50])
    assert splitter.should_split(small + small + small)


def test_single_page_pdf_is_never_split_even_over_threshold():
    splitter = PdfSplitter(threshold_bytes=10)
    file_bytes = make_pdf_bytes(["the only page, but the file itself is 'oversized'"])
    assert splitter.split(file_bytes, chunk_size=800, chunk_overlap=100) == [file_bytes]


def test_split_produces_multiple_independently_parseable_parts_with_overlap():
    pages = [f"page {i} unique marker {i:03d}" for i in range(10)]
    file_bytes = make_pdf_bytes(pages)
    chunk_size, chunk_overlap = 10, 1
    target_part_bytes = len(file_bytes) // 5
    splitter = PdfSplitter(threshold_bytes=10, target_part_bytes=target_part_bytes, max_parts=20)

    parts = splitter.split(file_bytes, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    assert len(parts) > 1
    for part in parts:
        # Every part must itself be a valid, independently parseable PDF.
        assert PdfReader(BytesIO(part)).pages

    # Recompute the exact plan splitter.split() used internally, to know how many pages of
    # overlap it actually settled on for these inputs.
    reader = PdfReader(BytesIO(file_bytes))
    total_pages = len(reader.pages)
    avg_chars_per_page = sum(len(p.extract_text() or "") for p in reader.pages) / total_pages
    plan = plan_split(
        total_pages=total_pages,
        total_bytes=len(file_bytes),
        avg_chars_per_page=avg_chars_per_page,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        target_part_bytes=target_part_bytes,
        max_parts=20,
    )
    assert len(parts) == plan.total_parts

    # Adjacent parts overlap: the previous part's trailing overlap_pages pages reappear verbatim
    # as this part's leading overlap_pages pages.
    for i in range(1, len(parts)):
        previous_texts = _page_texts(parts[i - 1])
        current_texts = _page_texts(parts[i])
        assert previous_texts[-plan.overlap_pages :] == current_texts[: plan.overlap_pages]

    # Every original page's marker text shows up in at least one part (nothing silently dropped).
    all_text = " ".join(text for part in parts for text in _page_texts(part))
    for i in range(10):
        assert f"marker {i:03d}" in all_text
