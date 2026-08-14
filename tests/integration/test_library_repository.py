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


def test_set_description_embedding_round_trip(db_session):
    repo = LibraryRepository(db_session)
    library = _create_library(repo, description="a library")
    db_session.commit()

    vector = [0.1] * EMBEDDING_DIM
    repo.set_description_embedding(library.id, vector)
    db_session.commit()

    candidates = repo.search_by_description_similarity(vector, top_n=10, min_similarity=0.0)
    assert [candidate.id for candidate, _similarity in candidates] == [library.id]


def test_list_all_with_description_excludes_libraries_without_one(db_session):
    repo = LibraryRepository(db_session)
    with_description = _create_library(repo, name="with-description", description="has one")
    _create_library(repo, name="without-description", description=None)
    db_session.commit()

    results = repo.list_all_with_description()

    assert [library.id for library in results] == [with_description.id]


def test_clear_all_description_embeddings(db_session):
    repo = LibraryRepository(db_session)
    library = _create_library(repo, description="a library")
    db_session.commit()
    repo.set_description_embedding(library.id, [0.1] * EMBEDDING_DIM)
    db_session.commit()

    repo.clear_all_description_embeddings()
    db_session.commit()

    candidates = repo.search_by_description_similarity([0.1] * EMBEDDING_DIM, top_n=10, min_similarity=0.0)
    assert candidates == []


def test_search_by_description_similarity_respects_min_similarity_and_top_n(db_session):
    repo = LibraryRepository(db_session)
    close = _create_library(repo, name="close", description="close")
    far = _create_library(repo, name="far", description="far")
    excluded = _create_library(repo, name="excluded", description="excluded")
    db_session.commit()

    # An exact match (similarity 1.0), a near match, and one deliberately excluded by threshold.
    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    near_vector = [0.9] + [0.1] * (EMBEDDING_DIM - 1)
    orthogonal_vector = [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2)
    repo.set_description_embedding(close.id, query_vector)
    repo.set_description_embedding(far.id, near_vector)
    repo.set_description_embedding(excluded.id, orthogonal_vector)
    db_session.commit()

    top_n_limited = repo.search_by_description_similarity(query_vector, top_n=1, min_similarity=0.0)
    assert [candidate.id for candidate, _similarity in top_n_limited] == [close.id]

    threshold_filtered = repo.search_by_description_similarity(query_vector, top_n=10, min_similarity=0.5)
    assert {candidate.id for candidate, _similarity in threshold_filtered} == {close.id, far.id}
    assert excluded.id not in {candidate.id for candidate, _similarity in threshold_filtered}
