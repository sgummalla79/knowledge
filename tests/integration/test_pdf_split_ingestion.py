import re
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.application.ingestion_service import IngestionService
from app.application.pdf_split_ingestion_service import PdfSplitIngestionService
from app.constants import EMBEDDING_DIM
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.auth.bootstrap import bootstrap_default_admin
from app.infrastructure.orm import Chunk
from app.infrastructure.parsing.pdf_splitter import PdfSplitter
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.user_repository import UserRepository
from tests.integration.conftest import seed_active_embedding_provider


def make_pdf_bytes(pages: list[str]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    for text in pages:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _fake_provider():
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    return provider


def _owner(db_session):
    bootstrap_default_admin(db_session)
    return UserRepository(db_session).get()


def _make_split_service(db_session, splitter=None):
    ingestion_service = IngestionService(
        DocumentRepository(db_session),
        ChunkRepository(db_session),
        EmbeddingSettingsRepository(db_session),
    )
    return PdfSplitIngestionService(ingestion_service, splitter), ingestion_service


def _chunk_text(db_session, document_id) -> str:
    rows = (
        db_session.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.ordinal)
        .all()
    )
    return " ".join(row.content for row in rows)


def test_pdf_below_threshold_ingests_as_single_document_unchanged(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    # Real default MAX_UPLOAD_MB threshold — this tiny synthetic PDF stays well under it.
    split_service, _ = _make_split_service(db_session)
    pdf_bytes = make_pdf_bytes(["just one small page"])

    results = []
    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        split_service.ingest(org_id, owner.id, "small.pdf", pdf_bytes, on_part_result=lambda *a: results.append(a))
    db_session.commit()

    assert len(results) == 1
    index, total, document, error = results[0]
    assert (index, total) == (1, 1)
    assert error is None
    assert document.status == "indexed"
    assert document.split_group_id is None
    assert document.split_part is None
    assert document.split_total is None
    assert document.title == "small.pdf"


def test_oversized_pdf_splits_into_multiple_documents_with_overlapping_content(db_session):
    owner = _owner(db_session)
    # chunk_size/chunk_overlap must be large relative to a single "marker NNN" token, or
    # TextChunker's own fixed-width windowing can chop a marker apart across two chunk rows —
    # a chunking artifact unrelated to what this test is actually verifying (PDF-level overlap).
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=200, chunk_overlap=20
    )
    db_session.commit()

    pages = [f"page {i} unique marker {i:03d}" for i in range(10)]
    pdf_bytes = make_pdf_bytes(pages)
    # Small injected threshold/target so this small synthetic PDF actually triggers a split —
    # same DI pattern TextChunker already uses, no real MAX_UPLOAD_MB-sized fixture needed.
    splitter = PdfSplitter(threshold_bytes=10, target_part_bytes=len(pdf_bytes) // 5, max_parts=20)
    split_service, _ = _make_split_service(db_session, splitter)

    results = []
    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        split_service.ingest(org_id, owner.id, "big.pdf", pdf_bytes, on_part_result=lambda *a: results.append(a))
    db_session.commit()

    assert len(results) > 1
    assert all(error is None for (_, _, _, error) in results)

    documents = DocumentRepository(db_session).list_for_org(org_id, limit=50, offset=0, sort="created_at")
    documents = sorted(documents, key=lambda d: d.split_part)
    total = len(documents)

    group_ids = {d.split_group_id for d in documents}
    assert len(group_ids) == 1
    for index, document in enumerate(documents, start=1):
        assert document.status == "indexed"
        assert document.file_type == "pdf"
        assert document.split_part == index
        assert document.split_total == total
        assert document.title == f"big.pdf (part {index} of {total})"

    # Boundary overlap: adjacent parts must share at least one page's marker text, and every
    # original page's marker must survive in at least one part (nothing silently dropped).
    marker_sets = [set(re.findall(r"marker \d{3}", _chunk_text(db_session, d.id))) for d in documents]
    assert set().union(*marker_sets) == {f"marker {i:03d}" for i in range(10)}
    for i in range(len(marker_sets) - 1):
        assert marker_sets[i] & marker_sets[i + 1], "adjacent split parts should share boundary content"


def test_one_failed_part_does_not_abort_the_others_and_is_independently_retryable(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=10, chunk_overlap=1
    )
    db_session.commit()

    pages = [f"page {i} unique marker {i:03d}" for i in range(9)]
    pdf_bytes = make_pdf_bytes(pages)
    splitter = PdfSplitter(threshold_bytes=10, target_part_bytes=len(pdf_bytes) // 3, max_parts=20)
    split_service, ingestion_service = _make_split_service(db_session, splitter)

    call_count = {"n": 0}

    def resolve_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("embedding API unavailable")
        return _fake_provider()

    results = []
    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        side_effect=resolve_side_effect,
    ):
        split_service.ingest(org_id, owner.id, "big.pdf", pdf_bytes, on_part_result=lambda *a: results.append(a))
    db_session.commit()

    assert len(results) == 3
    failed_results = [r for r in results if r[3] is not None]
    succeeded_results = [r for r in results if r[3] is None]
    assert len(failed_results) == 1
    assert len(succeeded_results) == 2

    documents = DocumentRepository(db_session).list_for_org(org_id, limit=50, offset=0, sort="created_at")
    statuses = {d.status for d in documents}
    assert statuses == {"indexed", "failed"}

    document_repo = DocumentRepository(db_session)
    failed_document = next(d for d in documents if d.status == "failed")
    assert document_repo.get_raw_bytes(failed_document.id) is not None
    assert failed_document.split_group_id is not None

    # The failed part retries independently, against its own stored bytes — no re-splitting.
    with patch(
        "app.application.ingestion_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(),
    ):
        retried_document = ingestion_service.retry(failed_document)
    db_session.commit()

    assert retried_document.status == "indexed"
    assert retried_document.split_group_id == failed_document.split_group_id
    assert retried_document.split_part == failed_document.split_part


def test_non_pdf_oversized_file_raises_file_too_large_without_creating_a_document(db_session):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    split_service, _ = _make_split_service(db_session)
    oversized = b"x" * (51 * 1024 * 1024)

    with pytest.raises(ValidationError) as exc_info:
        split_service.ingest(org_id, owner.id, "huge.md", oversized)
    assert exc_info.value.code == error_codes.FILE_TOO_LARGE

    documents = DocumentRepository(db_session).list_for_org(org_id, limit=10, offset=0, sort="created_at")
    assert documents == []
