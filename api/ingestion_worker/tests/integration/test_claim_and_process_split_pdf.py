from io import BytesIO
from unittest.mock import MagicMock, patch

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from api.constants import EMBEDDING_DIM
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.parsing.pdf_splitter import PdfSplitter
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.ingestion_job_repository import IngestionJobRepository
from api.ingestion_worker.tests.integration.conftest import seed_active_embedding_provider
from api.ingestion_worker.worker import IngestionJobWorker


def _make_pdf_bytes(pages: list[str]) -> bytes:
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
    bootstrap_default_identity(db_session)
    return IdentityRepository(db_session).get()


def test_worker_processes_an_oversized_pdf_into_multiple_parts(db_session, session_factory, storage):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=200, chunk_overlap=20
    )
    pdf_bytes = _make_pdf_bytes([f"page {i} unique marker {i:03d}" for i in range(10)])
    payload_path = "org/job/upload.bin"
    storage.save_bytes(payload_path, pdf_bytes)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(
        org_id, type="upload", triggered_by=owner.id, payload_path=payload_path, payload_filename="big.pdf"
    )
    db_session.commit()

    # Small injected threshold so this small synthetic PDF actually triggers a split -- same DI
    # pattern api/tests/integration/test_pdf_split_ingestion.py's _make_split_service uses.
    splitter = PdfSplitter(threshold_bytes=10, target_part_bytes=len(pdf_bytes) // 5, max_parts=20)
    worker = IngestionJobWorker(session_factory=session_factory, pdf_splitter=splitter, storage=storage)
    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve", return_value=_fake_provider()
    ):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    assert refreshed.status == "indexed"
    assert refreshed.parts_total is not None and refreshed.parts_total > 1
    assert refreshed.parts_completed == refreshed.parts_total
    assert refreshed.parts_failed == 0
    assert len(refreshed.document_ids) == refreshed.parts_total
    assert refreshed.items_processed == refreshed.parts_completed
    assert refreshed.payload_path is None
    assert not storage.resolve(payload_path).exists()

    documents = DocumentRepository(verify_session).list_for_org(org_id, limit=50, offset=0, sort="created_at")
    assert len(documents) == refreshed.parts_total
    assert all(d.status == "indexed" for d in documents)
    verify_session.close()


def test_worker_marks_indexed_with_partial_success_when_one_part_fails(db_session, session_factory, storage):
    owner = _owner(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=10, chunk_overlap=1
    )
    pdf_bytes = _make_pdf_bytes([f"page {i} unique marker {i:03d}" for i in range(9)])
    payload_path = "org/job/upload.bin"
    storage.save_bytes(payload_path, pdf_bytes)
    ingestion_jobs = IngestionJobRepository(db_session)
    job = ingestion_jobs.create(
        org_id, type="upload", triggered_by=owner.id, payload_path=payload_path, payload_filename="big.pdf"
    )
    db_session.commit()

    splitter = PdfSplitter(threshold_bytes=10, target_part_bytes=len(pdf_bytes) // 3, max_parts=20)
    worker = IngestionJobWorker(session_factory=session_factory, pdf_splitter=splitter, storage=storage)

    call_count = {"n": 0}

    def resolve_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("embedding API unavailable")
        return _fake_provider()

    with patch(
        "api.application.ingestion_service.EmbeddingProviderRegistry.resolve", side_effect=resolve_side_effect
    ):
        claimed = worker.claim_and_process_one()

    assert claimed is True

    verify_session = session_factory()
    refreshed = IngestionJobRepository(verify_session).get(job.id)
    assert refreshed.status == "indexed"  # partial success -- at least one part completed
    assert refreshed.parts_failed == 1
    assert refreshed.parts_completed >= 1
    verify_session.close()
