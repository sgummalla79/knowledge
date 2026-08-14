from unittest.mock import MagicMock, patch

from app.application.library_router_service import LibraryRouterService
from app.application.retrieval_service import RetrievalService
from app.constants import EMBEDDING_DIM
from app.infrastructure.orm import Document
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.library_repository import LibraryRepository
from app.infrastructure.repositories.router_settings_repository import RouterSettingsRepository
from app.infrastructure.repositories.search_settings_repository import SearchSettingsRepository
from tests.integration.conftest import seed_active_embedding_provider

# Real DB, real repos, real RRF — only the outbound embedding provider call is faked (same
# convention tests/integration/test_retrieval_service.py uses). Route-level HTTP wiring is covered
# by the mocked tests/unit/test_router_query_routes.py.


def _fake_provider(query_vector):
    provider = MagicMock()
    provider.embed_query.return_value = query_vector
    return provider


def _make_document(db_session, library_id):
    document = Document(
        library_id=library_id,
        source_filename="notes.md",
        file_type="md",
        content_hash="abc",
        status="completed",
    )
    db_session.add(document)
    db_session.flush()
    return document


def _make_router_service(db_session):
    library_repo = LibraryRepository(db_session)
    embedding_settings_repo = EmbeddingSettingsRepository(db_session)
    search_settings_repo = SearchSettingsRepository(db_session)
    return LibraryRouterService(
        library_repo,
        embedding_settings_repo,
        RouterSettingsRepository(db_session),
        search_settings_repo,
        RetrievalService(library_repo, ChunkRepository(db_session), embedding_settings_repo, search_settings_repo),
    )


def test_query_routes_to_the_matching_library_and_excludes_the_unrelated_one(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library_a = library_repo.create(name="alpha-lib", description="alpha topic")
    library_b = library_repo.create(name="beta-lib", description="beta topic")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    orthogonal_vector = [0.0] * (EMBEDDING_DIM - 1) + [1.0]

    # library_a's description is identical to the query (similarity 1.0), library_b's is
    # orthogonal (similarity 0.0) — well clear of the default min_similarity threshold either way.
    library_repo.set_description_embedding(library_a.id, query_vector)
    library_repo.set_description_embedding(library_b.id, orthogonal_vector)
    db_session.commit()

    document_a = _make_document(db_session, library_a.id)
    chunk_repo.bulk_create(document_a.id, library_a.id, [(0, "alpha content chunk", query_vector)])
    document_b = _make_document(db_session, library_b.id)
    chunk_repo.bulk_create(document_b.id, library_b.id, [(0, "beta content chunk", orthogonal_vector)])
    db_session.commit()

    service = _make_router_service(db_session)
    with patch(
        "app.application.library_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query("find alpha content", top_k=5)

    assert len(results) == 1
    assert results[0].library_id == library_a.id
    assert results[0].library_name == "alpha-lib"
    assert results[0].chunk.content == "alpha content chunk"


def test_query_merges_results_from_multiple_matching_libraries(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library_a = library_repo.create(name="alpha-lib", description="alpha topic")
    library_b = library_repo.create(name="also-alpha-lib", description="also about alpha")
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    library_repo.set_description_embedding(library_a.id, query_vector)
    library_repo.set_description_embedding(library_b.id, query_vector)
    db_session.commit()

    document_a = _make_document(db_session, library_a.id)
    chunk_repo.bulk_create(document_a.id, library_a.id, [(0, "alpha chunk one", query_vector)])
    document_b = _make_document(db_session, library_b.id)
    chunk_repo.bulk_create(document_b.id, library_b.id, [(0, "alpha chunk two", query_vector)])
    db_session.commit()

    service = _make_router_service(db_session)
    with patch(
        "app.application.library_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query("find alpha content", top_k=5)

    assert {result.library_id for result in results} == {library_a.id, library_b.id}
    assert {result.chunk.content for result in results} == {"alpha chunk one", "alpha chunk two"}


def test_query_returns_empty_list_when_no_library_has_a_description_embedding(db_session):
    library_repo = LibraryRepository(db_session)
    library_repo.create(name="no-description-lib", description=None)
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    service = _make_router_service(db_session)
    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    with patch(
        "app.application.library_router_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query("hello", top_k=5)

    assert results == []
