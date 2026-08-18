from unittest.mock import MagicMock, patch

from app.application.category_router_service import CategoryRouterService
from app.application.retrieval_service import RetrievalService
from app.constants import EMBEDDING_DIM
from app.infrastructure.auth.bootstrap import bootstrap_default_admin
from app.infrastructure.orm import Document
from app.infrastructure.repositories.category_repository import CategoryRepository
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.user_repository import UserRepository
from tests.integration.conftest import seed_active_embedding_provider

# Real DB, real repos, real RRF — only the outbound embedding provider call is faked (same
# convention tests/integration/test_retrieval_service.py uses). Route-level HTTP wiring is covered
# by the mocked tests/unit/test_router_query_routes.py.


def _fake_provider(query_vector):
    provider = MagicMock()
    provider.embed_query.return_value = query_vector
    return provider


def _owner(db_session):
    bootstrap_default_admin(db_session)
    return UserRepository(db_session).get()


def _make_document(db_session, org_id, owner_id):
    document = Document(
        org_id=org_id,
        owner_id=owner_id,
        title="notes.md",
        type="article",
        file_type="md",
        content_hash="abc",
        status="indexed",
    )
    db_session.add(document)
    db_session.flush()
    return document


def _make_router_service(db_session):
    category_repo = CategoryRepository(db_session)
    embedding_settings_repo = EmbeddingSettingsRepository(db_session)
    return CategoryRouterService(
        category_repo,
        embedding_settings_repo,
        RetrievalService(ChunkRepository(db_session), embedding_settings_repo),
    )


def test_query_routes_to_the_matching_category_and_excludes_the_unrelated_one(db_session):
    owner = _owner(db_session)
    category_repo = CategoryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    category_a = category_repo.create(org_id, name="alpha-cat", slug="alpha-cat", description="alpha topic")
    category_b = category_repo.create(org_id, name="beta-cat", slug="beta-cat", description="beta topic")
    db_session.commit()
    embedding_model_id = EmbeddingSettingsRepository(db_session).get(org_id).id

    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    orthogonal_vector = [0.0] * (EMBEDDING_DIM - 1) + [1.0]

    # category_a's description is identical to the query (similarity 1.0), category_b's is
    # orthogonal (similarity 0.0) — well clear of the default min_similarity threshold either way.
    category_repo.set_description_embedding(category_a.id, query_vector)
    category_repo.set_description_embedding(category_b.id, orthogonal_vector)
    db_session.commit()

    document_a = _make_document(db_session, org_id, owner.id)
    document_a.category_id = category_a.id
    document_b = _make_document(db_session, org_id, owner.id)
    document_b.category_id = category_b.id
    db_session.flush()
    chunk_repo.bulk_create(document_a.id, org_id, embedding_model_id, [(0, "alpha content chunk", 5, query_vector)])
    chunk_repo.bulk_create(document_b.id, org_id, embedding_model_id, [(0, "beta content chunk", 5, orthogonal_vector)])
    db_session.commit()

    service = _make_router_service(db_session)
    with patch(
        "app.application.category_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query(org_id, "find alpha content", top_k=5)

    assert len(results) == 1
    assert results[0].category_id == category_a.id
    assert results[0].category_name == "alpha-cat"
    assert results[0].chunk.content == "alpha content chunk"


def test_query_merges_results_from_multiple_matching_categories(db_session):
    owner = _owner(db_session)
    category_repo = CategoryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    category_a = category_repo.create(org_id, name="alpha-cat", slug="alpha-cat", description="alpha topic")
    category_b = category_repo.create(org_id, name="also-alpha-cat", slug="also-alpha-cat", description="also about alpha")
    db_session.commit()
    embedding_model_id = EmbeddingSettingsRepository(db_session).get(org_id).id

    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    category_repo.set_description_embedding(category_a.id, query_vector)
    category_repo.set_description_embedding(category_b.id, query_vector)
    db_session.commit()

    document_a = _make_document(db_session, org_id, owner.id)
    document_a.category_id = category_a.id
    document_b = _make_document(db_session, org_id, owner.id)
    document_b.category_id = category_b.id
    db_session.flush()
    chunk_repo.bulk_create(document_a.id, org_id, embedding_model_id, [(0, "alpha chunk one", 5, query_vector)])
    chunk_repo.bulk_create(document_b.id, org_id, embedding_model_id, [(0, "alpha chunk two", 5, query_vector)])
    db_session.commit()

    service = _make_router_service(db_session)
    with patch(
        "app.application.category_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query(org_id, "find alpha content", top_k=5)

    assert {result.category_id for result in results} == {category_a.id, category_b.id}
    assert {result.chunk.content for result in results} == {"alpha chunk one", "alpha chunk two"}


def test_query_returns_empty_list_when_no_category_has_a_description_embedding(db_session):
    category_repo = CategoryRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    category_repo.create(org_id, name="no-description-cat", slug="no-description-cat", description=None)
    db_session.commit()

    service = _make_router_service(db_session)
    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    with patch(
        "app.application.category_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query(org_id, "hello", top_k=5)

    assert results == []
