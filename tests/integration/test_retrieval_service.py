from unittest.mock import MagicMock, patch

import pytest

from app.application.retrieval_service import RetrievalService
from app.constants import EMBEDDING_DIM
from app.domain import error_codes
from app.domain.errors import ValidationError
from app.infrastructure.auth.bootstrap import bootstrap_default_admin, bootstrap_default_organization
from app.infrastructure.orm import Document
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from app.infrastructure.repositories.user_repository import UserRepository
from tests.integration.conftest import seed_active_embedding_provider


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


def _make_service(db_session):
    return RetrievalService(
        ChunkRepository(db_session),
        EmbeddingSettingsRepository(db_session),
    )


def test_query_returns_nearest_chunks_ranked_by_hybrid_fusion(db_session):
    owner = _owner(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()
    embedding_model_id = EmbeddingSettingsRepository(db_session).get(org_id).id

    near = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    far = [0.0] * (EMBEDDING_DIM - 1) + [1.0]

    document = _make_document(db_session, org_id, owner.id)
    chunk_repo.bulk_create(
        document.id,
        org_id,
        embedding_model_id,
        [(0, "closest chunk", 5, near), (1, "farthest chunk", 5, far)],
    )
    db_session.commit()

    service = _make_service(db_session)
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(near),
    ):
        results = service.query(org_id, "find the closest chunk", top_k=2)

    # Both dense (embedding distance) and sparse (keyword overlap on "closest"/"chunk") agree here,
    # so fusion doesn't change the obvious ordering — this is the "fusion didn't regress an
    # obvious match" sanity check called out in the plan's verification steps.
    assert [chunk.content for chunk in results] == ["closest chunk", "farthest chunk"]


def test_hybrid_fusion_promotes_sparse_match_over_pure_dense_order(db_session):
    owner = _owner(db_session)
    chunk_repo = ChunkRepository(db_session)
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()
    embedding_model_id = EmbeddingSettingsRepository(db_session).get(org_id).id

    query_vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    closest = [1.0] + [0.0] * (EMBEDDING_DIM - 1)  # identical to query — dense rank 1
    middle = [0.7071] * 2 + [0.0] * (EMBEDDING_DIM - 2)  # dense rank 2
    farthest = [0.0] * (EMBEDDING_DIM - 1) + [1.0]  # orthogonal to query — dense rank 3

    document = _make_document(db_session, org_id, owner.id)
    chunk_repo.bulk_create(
        document.id,
        org_id,
        embedding_model_id,
        [
            (0, "generic filler text about nothing in particular", 5, closest),
            (1, "more generic filler with no special terms", 5, middle),
            (2, "zephyrpineapple is the unique marker phrase here", 5, farthest),
        ],
    )
    db_session.commit()

    service = _make_service(db_session)
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(query_vector),
    ):
        results = service.query(org_id, "zephyrpineapple", top_k=3)

    # Dense-only would rank this chunk last (it's the farthest embedding) — hybrid fusion
    # promotes it to first because it's the only chunk that actually matches the query keyword.
    assert results[0].content == "zephyrpineapple is the unique marker phrase here"


def test_query_with_no_chunks_returns_empty(db_session):
    org = bootstrap_default_organization(db_session)
    seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=800, chunk_overlap=100
    )
    db_session.commit()

    service = _make_service(db_session)
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider([0.0] * EMBEDDING_DIM),
    ):
        results = service.query(org.id, "hello", top_k=5)

    assert results == []


def test_query_without_configured_embeddings_raises(db_session):
    org = bootstrap_default_organization(db_session)
    db_session.commit()

    service = _make_service(db_session)
    with pytest.raises(ValidationError) as exc_info:
        service.query(org.id, "hello", top_k=5)
    assert exc_info.value.code == error_codes.EMBEDDINGS_NOT_CONFIGURED
