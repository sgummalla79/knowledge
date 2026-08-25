from pathlib import Path

import pdfplumber

from api.infrastructure.parsing.base import DocumentParser


class PdfParser(DocumentParser):
    """Uses pdfplumber (font-metrics/layout-aware word reconstruction) rather than pypdf's
    glyph-gap heuristic, which regularly splits words mid-token on kerned or justified PDF text
    (e.g. "agent" -> "ag ent") and corrupts retrieval/embedding quality downstream. pypdf is still
    used in pdf_splitter.py, where only page count and a rough per-page character density feed
    split-size math — text fidelity doesn't matter there the way it does for ingested content."""

    def parse(self, path: str | Path) -> str:
        # pdfplumber.open() takes a path directly and reads from disk -- no need to have already
        # loaded the whole file into memory as bytes first (see docs/UPLOAD_STORAGE_REDESIGN.md).
        #
        # page.close() flushes pdfplumber's per-page caches (.chars/.rects/.lines/.layout, each a
        # real Python object per glyph/line/rect on that page) right after that page's text is
        # pulled -- without it, every page's cache stays alive for the whole document, since
        # PDF.close() (the outer context manager) only releases them at the very end, after the
        # peak has already happened. Confirmed in production: a 41.5MB, page/layout-dense PDF
        # OOM-killed a 4Gi worker process during parsing alone, before chunking ever started, with
        # every page's parsed structure held simultaneously. try/finally so a page that fails to
        # extract still gets its cache released rather than leaking on the error path too.
        texts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                try:
                    texts.append(page.extract_text() or "")
                finally:
                    page.close()
        return "\n".join(texts)
