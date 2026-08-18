from dataclasses import dataclass
from io import BytesIO
from math import ceil, floor

from pypdf import PdfReader, PdfWriter

from api.constants import (
    MAX_UPLOAD_MB,
    PDF_SPLIT_MAX_OVERLAP_PAGES,
    PDF_SPLIT_MAX_PARTS,
    PDF_SPLIT_MIN_OVERLAP_PAGES,
    PDF_SPLIT_OVERLAP_SAFETY_FACTOR,
    PDF_SPLIT_TARGET_PART_MB,
)
from api.domain import error_codes
from api.domain.errors import ValidationError


@dataclass(frozen=True)
class SplitPlan:
    total_parts: int
    pages_per_part: int
    overlap_pages: int


def plan_split(
    total_pages: int,
    total_bytes: int,
    avg_chars_per_page: float,
    chunk_size: int,
    chunk_overlap: int,
    target_part_bytes: int,
    max_parts: int,
) -> SplitPlan:
    """Pure arithmetic, no pypdf dependency — how many pages go in each part, and how many of a
    part's leading pages are duplicated from the previous part's trailing pages, so a chunking
    window can bridge whatever content originally straddled that page boundary.

    Overlap is sized off chunk_size + chunk_overlap (the actual per-document chunking window),
    scaled by PDF_SPLIT_OVERLAP_SAFETY_FACTOR, converted to a page count via this document's own
    average text density — not a flat "1 page" guess, since page density varies hugely between a
    dense text page and a mostly-whitespace or scanned one.
    """
    avg_bytes_per_page = max(total_bytes / total_pages, 1)
    pages_per_part = max(1, floor(target_part_bytes / avg_bytes_per_page))

    target_overlap_chars = PDF_SPLIT_OVERLAP_SAFETY_FACTOR * (chunk_size + chunk_overlap)
    overlap_pages = ceil(target_overlap_chars / max(avg_chars_per_page, 1))
    overlap_pages = min(max(overlap_pages, PDF_SPLIT_MIN_OVERLAP_PAGES), PDF_SPLIT_MAX_OVERLAP_PAGES)

    # A part must be able to contain at least one page beyond what it borrows from the previous
    # part's tail, or "core" pages (the ones that actually advance through the document) would
    # never grow.
    if pages_per_part <= overlap_pages:
        pages_per_part = overlap_pages + 1

    total_parts = ceil(total_pages / pages_per_part)
    if total_parts > max_parts:
        raise ValidationError(
            error_codes.PDF_SPLIT_TOO_MANY_PARTS,
            f"This PDF would need to be split into {total_parts} parts, more than the "
            f"{max_parts}-part limit. Split it manually into smaller files before uploading.",
        )

    return SplitPlan(total_parts=total_parts, pages_per_part=pages_per_part, overlap_pages=overlap_pages)


class PdfSplitter:
    """Splits an oversized PDF into multiple smaller PDFs (raw bytes, pre-parse) so each part can
    flow through the existing IngestionService pipeline unmodified. Constructor-injectable
    thresholds mirror TextChunker's DI pattern, so tests can exercise splitting without needing a
    real MAX_UPLOAD_MB-sized fixture."""

    def __init__(
        self,
        threshold_bytes: int = MAX_UPLOAD_MB * 1024 * 1024,
        target_part_bytes: int = PDF_SPLIT_TARGET_PART_MB * 1024 * 1024,
        max_parts: int = PDF_SPLIT_MAX_PARTS,
    ):
        self.threshold_bytes = threshold_bytes
        self.target_part_bytes = target_part_bytes
        self.max_parts = max_parts

    def should_split(self, file_bytes: bytes) -> bool:
        return len(file_bytes) > self.threshold_bytes

    def split(self, file_bytes: bytes, chunk_size: int, chunk_overlap: int) -> list[bytes]:
        """Always returns a list — [file_bytes] unchanged when splitting isn't needed or isn't
        possible (e.g. a single huge page), so callers never special-case the non-split path."""
        if not self.should_split(file_bytes):
            return [file_bytes]

        reader = PdfReader(BytesIO(file_bytes))
        total_pages = len(reader.pages)
        if total_pages <= 1:
            return [file_bytes]

        total_chars = sum(len(page.extract_text() or "") for page in reader.pages)
        avg_chars_per_page = total_chars / total_pages

        plan = plan_split(
            total_pages=total_pages,
            total_bytes=len(file_bytes),
            avg_chars_per_page=avg_chars_per_page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            target_part_bytes=self.target_part_bytes,
            max_parts=self.max_parts,
        )
        if plan.total_parts <= 1:
            return [file_bytes]

        parts = []
        for part_index in range(plan.total_parts):
            core_start = part_index * plan.pages_per_part
            core_end = min(core_start + plan.pages_per_part, total_pages)
            # Only the core segment (not the borrowed overlap prefix) advances the start of the
            # *next* part — otherwise overlap would compound across many parts instead of staying
            # bounded to one segment's worth of boundary content.
            part_start = core_start if part_index == 0 else max(core_start - plan.overlap_pages, 0)

            writer = PdfWriter()
            for page_number in range(part_start, core_end):
                writer.add_page(reader.pages[page_number])
            buffer = BytesIO()
            writer.write(buffer)
            parts.append(buffer.getvalue())

        return parts
