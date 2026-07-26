import threading
from uuid import UUID

from app.application.ingestion_service import IngestionService
from app.application.job_store import JobNotFoundError, JobStore
from app.domain import error_codes
from app.domain.entities import Document
from app.domain.errors import NotFoundError
from app.domain.ports import DocumentRepositoryPort, LibraryRepositoryPort
from app.infrastructure.orm import SessionLocal
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.library_repository import LibraryRepository


class DocumentService:
    def __init__(self, document_repo: DocumentRepositoryPort, library_repo: LibraryRepositoryPort):
        self._documents = document_repo
        self._libraries = library_repo

    def list_documents(self, library_id: UUID, limit: int, offset: int, sort: str) -> tuple[list[Document], int]:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")
        return (
            self._documents.list_for_library(library_id, limit, offset, sort),
            self._documents.count_for_library(library_id),
        )

    def get_job_status(self, job_id: str) -> dict:
        try:
            return JobStore.get(job_id)
        except JobNotFoundError as error:
            raise NotFoundError(error_codes.JOB_NOT_FOUND, "Job not found.") from error

    def start_ingestion(self, library_id: UUID, filename: str, file_bytes: bytes) -> str:
        if self._libraries.get(library_id) is None:
            raise NotFoundError(error_codes.LIBRARY_NOT_FOUND, "Library not found.")

        job_id = JobStore.create()
        thread = threading.Thread(
            target=_run_ingestion_job,
            args=(job_id, library_id, filename, file_bytes),
            daemon=True,
        )
        thread.start()
        return job_id


def _run_ingestion_job(job_id: str, library_id: UUID, filename: str, file_bytes: bytes):
    # Runs on a background thread with no Flask request context, so it gets its own session
    # independent of the request-scoped one from container.get_session() (which relies on
    # flask.g, unavailable here) — and commits/rolls back that session directly.
    session = SessionLocal()
    try:
        JobStore.mark_running(job_id)
        library_repo = LibraryRepository(session)
        library = library_repo.get(library_id)
        ingestion_service = IngestionService(library_repo, DocumentRepository(session), ChunkRepository(session))
        document = ingestion_service.ingest(library, filename, file_bytes)
        session.commit()
        JobStore.mark_completed(job_id, document.id)
    except Exception as error:
        session.commit()
        JobStore.mark_failed(job_id, error)
    finally:
        session.close()
