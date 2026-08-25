import hashlib
import shutil
from pathlib import Path
from uuid import UUID

# Chunk size for streaming a file through hashlib / a save — large enough to be efficient, small
# enough that a MAX_REQUEST_BODY_MB-sized file is never held in memory anywhere near its full size
# at once. Not sourced from anywhere else (no equivalent "read chunk size" constant exists in this
# codebase yet) — a library-level tuning value, not something that changes without a redeploy.
_STREAM_CHUNK_BYTES = 1024 * 1024

# Fixed filename, not the caller's original filename -- same reasoning
# docs/UPLOAD_STORAGE_REDESIGN.md gives for ingestion_jobs' own upload.bin: the real filename is
# already tracked in ingestion_jobs.payload_filename / documents.title, there's nothing to gain
# from also encoding it in the path, and every path segment stays a server-generated UUID with no
# user-controlled path-traversal surface to sanitize.
_JOB_UPLOAD_FILENAME = "upload.bin"


class UploadStorage:
    """Local-disk storage for raw uploaded/ingested file bytes -- see
    docs/UPLOAD_STORAGE_REDESIGN.md for why this replaced storing them as Postgres bytea values.
    A concrete infra class, not a Protocol port (this repo only ports repositories -- PdfSplitter/
    WebPageFetcher/ParserRegistry are the precedent for a directly-injected concrete class here
    too); swapping to networked storage (MinIO) if this cluster ever grows a second node is a
    documented future redesign, not a reason to add an abstraction layer now.

    Every path this class builds or accepts is relative to `root` and built only from
    server-generated UUIDs -- callers never pass user-supplied strings (filenames, etc.) into a
    path.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path_for_job_upload(self, org_id: UUID, job_id: UUID) -> str:
        return f"{org_id}/{job_id}/{_JOB_UPLOAD_FILENAME}"

    def path_for_document(self, org_id: UUID, document_id: UUID) -> str:
        return f"{org_id}/documents/{document_id}.bin"

    def path_for_part(self, org_id: UUID, job_id: UUID, index: int) -> str:
        return f"{org_id}/{job_id}/parts/part-{index}.bin"

    def resolve(self, relative_path: str) -> Path:
        """Absolute path for read-only use (e.g. handing to pdfplumber/PdfReader directly)."""
        return self.root / relative_path

    def save_stream(self, relative_path: str, file_storage) -> None:
        """Streams a Werkzeug FileStorage (an incoming upload) straight to disk --
        FileStorage.save() reads from the WSGI input in chunks itself, so the whole file is never
        materialized as one Python bytes object in this process."""
        destination = self.resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)

    def save_bytes(self, relative_path: str, data: bytes) -> None:
        """For callers that already hold bytes in memory (a PDF split part, or crawled HTML) --
        both are bounded/small by construction, so a plain write is fine here."""
        destination = self.resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    def move_into(self, source_relative_path: str, dest_relative_path: str) -> None:
        """Transfers ownership of a file already on disk to a new path -- same-filesystem atomic
        rename in the common case (shutil.move falls back to copy+delete only if the two paths
        ever land on different filesystems, which doesn't happen here since every path is under
        the same `root`)."""
        source = self.resolve(source_relative_path)
        destination = self.resolve(dest_relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, destination)

    def delete(self, relative_path: str | None) -> None:
        """No-op for a path that's None or already gone -- callers use this both for a real
        cleanup (a document reaching `indexed`) and for a path whose file may have already been
        moved away by move_into() (see IngestionService.ingest()), so "already absent" is an
        expected outcome, not an error."""
        if relative_path is None:
            return
        self.resolve(relative_path).unlink(missing_ok=True)

    def size(self, relative_path: str) -> int:
        return self.resolve(relative_path).stat().st_size

    def sha256_and_size(self, relative_path: str) -> tuple[str, int]:
        """Streamed in fixed-size chunks rather than a single read_bytes() -- see
        _STREAM_CHUNK_BYTES's own comment."""
        digest = hashlib.sha256()
        size = 0
        with self.resolve(relative_path).open("rb") as f:
            while chunk := f.read(_STREAM_CHUNK_BYTES):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size
