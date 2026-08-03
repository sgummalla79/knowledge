import pytest
from sqlalchemy import text

from app.constants import EMBEDDING_DIM
from app.domain.errors import ConflictError
from app.infrastructure.orm import Chunk, Document
from app.infrastructure.repositories.library_repository import LibraryRepository


def _create_library(repo, **overrides):
    fields = {
        "name": "test-library",
        "description": None,
    }
    fields.update(overrides)
    return repo.create(**fields)


def test_create_and_get_round_trip(db_session):
    repo = LibraryRepository(db_session)
    created = _create_library(repo)
    db_session.commit()

    fetched = repo.get(created.id)
    assert fetched.id == created.id
    assert fetched.name == "test-library"
    assert fetched.document_count == 0


def test_get_missing_returns_none(db_session):
    repo = LibraryRepository(db_session)
    assert repo.get("00000000-0000-0000-0000-000000000000") is None


def test_update_renames_library(db_session):
    repo = LibraryRepository(db_session)
    library = _create_library(repo, name="old-name", description="old description")
    db_session.commit()

    updated = repo.update(library.id, name="new-name", description="new description")
    db_session.commit()

    assert updated.name == "new-name"
    assert updated.description == "new description"
    fetched = repo.get(library.id)
    assert fetched.name == "new-name"
    assert fetched.description == "new description"


def test_update_duplicate_name_raises_conflict(db_session):
    repo = LibraryRepository(db_session)
    _create_library(repo, name="taken")
    other = _create_library(repo, name="other")
    db_session.commit()

    with pytest.raises(ConflictError):
        repo.update(other.id, name="taken", description=None)


def test_duplicate_name_raises_conflict(db_session):
    repo = LibraryRepository(db_session)
    _create_library(repo, name="dup")
    db_session.commit()

    with pytest.raises(ConflictError):
        _create_library(repo, name="dup")


def test_list_respects_limit_offset_and_sort(db_session):
    repo = LibraryRepository(db_session)
    _create_library(repo, name="alpha")
    _create_library(repo, name="beta")
    _create_library(repo, name="gamma")
    db_session.commit()

    ascending = repo.list(limit=10, offset=0, sort="name")
    assert [library.name for library in ascending] == ["alpha", "beta", "gamma"]

    first_page = repo.list(limit=2, offset=0, sort="name")
    second_page = repo.list(limit=2, offset=2, sort="name")
    assert [library.name for library in first_page] == ["alpha", "beta"]
    assert [library.name for library in second_page] == ["gamma"]

    assert repo.count() == 3


def test_increment_counts(db_session):
    repo = LibraryRepository(db_session)
    library = _create_library(repo)
    db_session.commit()

    repo.increment_counts(library.id, document_delta=1, chunk_delta=5)
    db_session.commit()

    updated = repo.get(library.id)
    assert updated.document_count == 1
    assert updated.chunk_count == 5


def test_delete_cascades_to_documents_and_chunks(db_session):
    repo = LibraryRepository(db_session)
    library = _create_library(repo)
    db_session.commit()

    document = Document(
        library_id=library.id,
        source_filename="notes.md",
        file_type="md",
        content_hash="abc123",
        status="completed",
    )
    db_session.add(document)
    db_session.flush()

    chunk = Chunk(
        document_id=document.id,
        library_id=library.id,
        chunk_index=0,
        content="hello world",
        embedding=[0.0] * EMBEDDING_DIM,
    )
    db_session.add(chunk)
    db_session.commit()

    # Capture plain values before the delete+commit below — expire_on_commit (SQLAlchemy's
    # default) expires `document`/`chunk` on commit, so accessing .id on them afterward would
    # trigger a refresh against a row Postgres's ON DELETE CASCADE has already removed.
    document_id = document.id
    chunk_id = chunk.id

    repo.delete(library.id)
    db_session.commit()

    document_count = db_session.execute(
        text("SELECT count(*) FROM documents WHERE id = :id"), {"id": document_id}
    ).scalar()
    chunk_count = db_session.execute(
        text("SELECT count(*) FROM chunks WHERE id = :id"), {"id": chunk_id}
    ).scalar()
    assert document_count == 0
    assert chunk_count == 0
