import pytest

from app.constants import EMBEDDING_DIM
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.document_repository import DocumentRepository
from app.infrastructure.repositories.library_repository import LibraryRepository


def test_bulk_create_failure_does_not_poison_the_session(db_session):
    """Regression test for a real incident: a NUL byte in chunk content made Postgres reject the
    insert ("A string literal cannot contain NUL (0x00) characters"), and without a savepoint that
    failure poisoned the whole session -- every later statement raised PendingRollbackError,
    including IngestionService._process()'s own "mark this document failed" write. The document
    row (already flushed earlier in the same uncommitted transaction) got silently wiped by the
    eventual rollback, and the job never reached completed *or* failed -- it just hung forever.
    bulk_create now scopes its insert to a SAVEPOINT, so a failure here only rolls back that
    savepoint, leaving the rest of the transaction (and the session itself) intact and usable.
    """
    library = LibraryRepository(db_session).create(name="chunk-savepoint-test", description=None)
    document = DocumentRepository(db_session).create(
        library_id=library.id,
        source_filename="notes.txt",
        file_type="txt",
        content_hash="deadbeef",
        status="processing",
    )
    db_session.commit()

    chunk_repo = ChunkRepository(db_session)
    with pytest.raises(Exception):
        chunk_repo.bulk_create(
            document.id, library.id, [(0, "bad content \x00 with a null byte", [0.0] * EMBEDDING_DIM)]
        )

    # Without the savepoint fix, this next statement on the same session would raise
    # PendingRollbackError instead of actually updating anything -- exactly what broke in prod.
    document_repo = DocumentRepository(db_session)
    updated = document_repo.update_status(document.id, "failed", error_message="bad content")
    db_session.commit()

    assert updated.status == "failed"
    assert document_repo.get(document.id).status == "failed"
