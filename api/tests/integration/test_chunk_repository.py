import pytest

from api.constants import EMBEDDING_DIM
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.tests.integration.conftest import seed_active_embedding_provider


def test_bulk_create_failure_does_not_poison_the_session(db_session):
    """Regression test for a real incident: a NUL byte in chunk content made Postgres reject the
    insert ("A string literal cannot contain NUL (0x00) characters"), and without a savepoint that
    failure poisoned the whole session -- every later statement raised PendingRollbackError,
    including IngestionService._process()'s own "mark this document failed" write. The document
    row (already flushed earlier in the same uncommitted transaction) got silently wiped by the
    eventual rollback, and the job never reached indexed *or* failed -- it just hung forever.
    bulk_create now scopes its insert to a SAVEPOINT, so a failure here only rolls back that
    savepoint, leaving the rest of the transaction (and the session itself) intact and usable.
    """
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    embedding_model_id = EmbeddingSettingsRepository(db_session).get(org_id).id

    document = DocumentRepository(db_session).create(
        org_id=org_id,
        owner_id=owner.id,
        title="notes.txt",
        type="article",
        file_type="txt",
        content_hash="deadbeef",
        status="processing",
    )
    db_session.commit()

    chunk_repo = ChunkRepository(db_session)
    with pytest.raises(Exception):
        chunk_repo.bulk_create(
            document.id,
            org_id,
            embedding_model_id,
            [(0, "bad content \x00 with a null byte", 5, [0.0] * EMBEDDING_DIM)],
        )

    # Without the savepoint fix, this next statement on the same session would raise
    # PendingRollbackError instead of actually updating anything -- exactly what broke in prod.
    document_repo = DocumentRepository(db_session)
    updated = document_repo.update_status(document.id, "failed", error_message="bad content")
    db_session.commit()

    assert updated.status == "failed"
    assert document_repo.get(document.id).status == "failed"
