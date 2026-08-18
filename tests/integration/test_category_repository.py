import pytest
from sqlalchemy import text

from app.constants import EMBEDDING_DIM
from app.domain.errors import ConflictError
from app.infrastructure.auth.bootstrap import bootstrap_default_organization
from app.infrastructure.orm import Document
from app.infrastructure.repositories.category_repository import CategoryRepository


def _create_category(repo, org_id, **overrides):
    fields = {
        "name": "test-category",
        "slug": "test-category",
        "description": None,
    }
    fields.update(overrides)
    return repo.create(org_id, **fields)


@pytest.fixture()
def org_id(db_session):
    return bootstrap_default_organization(db_session).id


def test_create_and_get_round_trip(db_session, org_id):
    repo = CategoryRepository(db_session)
    created = _create_category(repo, org_id)
    db_session.commit()

    fetched = repo.get(created.id)
    assert fetched.id == created.id
    assert fetched.org_id == org_id
    assert fetched.name == "test-category"
    assert fetched.slug == "test-category"


def test_get_missing_returns_none(db_session):
    repo = CategoryRepository(db_session)
    assert repo.get("00000000-0000-0000-0000-000000000000") is None


def test_update_renames_category(db_session, org_id):
    repo = CategoryRepository(db_session)
    category = _create_category(repo, org_id, name="old-name", slug="old-name", description="old description")
    db_session.commit()

    updated = repo.update(category.id, name="new-name", description="new description")
    db_session.commit()

    assert updated.name == "new-name"
    assert updated.description == "new description"
    fetched = repo.get(category.id)
    assert fetched.name == "new-name"
    assert fetched.description == "new description"


def test_duplicate_slug_within_org_raises_conflict(db_session, org_id):
    repo = CategoryRepository(db_session)
    _create_category(repo, org_id, name="dup", slug="dup")
    db_session.commit()

    with pytest.raises(ConflictError):
        _create_category(repo, org_id, name="dup again", slug="dup")


def test_list_by_org_returns_only_that_orgs_categories(db_session, org_id):
    repo = CategoryRepository(db_session)
    _create_category(repo, org_id, name="alpha", slug="alpha")
    _create_category(repo, org_id, name="beta", slug="beta")
    db_session.commit()

    categories = repo.list_by_org(org_id)
    assert {category.slug for category in categories} == {"alpha", "beta"}


def test_delete_sets_null_on_documents_instead_of_cascading(db_session, org_id):
    """documents.category_id has ON DELETE SET NULL (a category is an optional grouping, not an
    owning relationship the way library_id used to be) — deleting a category must leave its
    documents intact, just uncategorized."""
    repo = CategoryRepository(db_session)
    category = _create_category(repo, org_id)
    db_session.commit()

    from app.infrastructure.repositories.user_repository import UserRepository
    from app.infrastructure.auth.bootstrap import bootstrap_default_admin

    bootstrap_default_admin(db_session)
    owner = UserRepository(db_session).get()

    document = Document(
        org_id=org_id,
        owner_id=owner.id,
        category_id=category.id,
        title="notes.md",
        type="article",
        file_type="md",
        content_hash="abc123",
        status="indexed",
    )
    db_session.add(document)
    db_session.commit()

    document_id = document.id

    repo.delete(category.id)
    db_session.commit()

    assert repo.get(category.id) is None
    remaining_category_id = db_session.execute(
        text("SELECT category_id FROM documents WHERE id = :id"), {"id": document_id}
    ).scalar()
    assert remaining_category_id is None


def test_set_description_embedding_round_trip(db_session, org_id):
    repo = CategoryRepository(db_session)
    category = _create_category(repo, org_id, description="a category")
    db_session.commit()

    vector = [0.1] * EMBEDDING_DIM
    repo.set_description_embedding(category.id, vector)
    db_session.commit()

    candidates = repo.search_by_description_similarity(org_id, vector, top_n=10, min_similarity=0.0)
    assert [candidate.id for candidate, _similarity in candidates] == [category.id]


def test_list_all_with_description_excludes_categories_without_one(db_session, org_id):
    repo = CategoryRepository(db_session)
    with_description = _create_category(
        repo, org_id, name="with-description", slug="with-description", description="has one"
    )
    _create_category(repo, org_id, name="without-description", slug="without-description", description=None)
    db_session.commit()

    results = repo.list_all_with_description(org_id)

    assert [category.id for category in results] == [with_description.id]


def test_clear_all_description_embeddings(db_session, org_id):
    repo = CategoryRepository(db_session)
    category = _create_category(repo, org_id, description="a category")
    db_session.commit()
    repo.set_description_embedding(category.id, [0.1] * EMBEDDING_DIM)
    db_session.commit()

    repo.clear_all_description_embeddings(org_id)
    db_session.commit()

    candidates = repo.search_by_description_similarity(org_id, [0.1] * EMBEDDING_DIM, top_n=10, min_similarity=0.0)
    assert candidates == []


def test_search_by_description_similarity_respects_min_similarity_and_top_n(db_session, org_id):
    repo = CategoryRepository(db_session)
    close = _create_category(repo, org_id, name="close", slug="close", description="close")
    far = _create_category(repo, org_id, name="far", slug="far", description="far")
    excluded = _create_category(repo, org_id, name="excluded", slug="excluded", description="excluded")
    db_session.commit()

    # An exact match (similarity 1.0), a near match (~0.99 — a small second component, not spread
    # across every remaining dimension, which would dilute cosine similarity via magnitude), and
    # one deliberately excluded by threshold (orthogonal, similarity 0.0).
    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    near_vector = [0.9, 0.1] + [0.0] * (EMBEDDING_DIM - 2)
    orthogonal_vector = [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2)
    repo.set_description_embedding(close.id, query_vector)
    repo.set_description_embedding(far.id, near_vector)
    repo.set_description_embedding(excluded.id, orthogonal_vector)
    db_session.commit()

    top_n_limited = repo.search_by_description_similarity(org_id, query_vector, top_n=1, min_similarity=0.0)
    assert [candidate.id for candidate, _similarity in top_n_limited] == [close.id]

    threshold_filtered = repo.search_by_description_similarity(org_id, query_vector, top_n=10, min_similarity=0.5)
    assert {candidate.id for candidate, _similarity in threshold_filtered} == {close.id, far.id}
    assert excluded.id not in {candidate.id for candidate, _similarity in threshold_filtered}
