from unittest.mock import MagicMock, patch

import pytest

from app.application.retrieval_service import RetrievalService
from app.constants import EMBEDDING_DIM
from app.domain.errors import NotFoundError
from app.infrastructure.orm import Document
from app.infrastructure.repositories.chunk_repository import ChunkRepository
from app.infrastructure.repositories.library_repository import LibraryRepository


def _fake_provider(query_vector):
    provider = MagicMock()
    provider.embed_query.return_value = query_vector
    return provider


def test_query_returns_nearest_chunks_ranked_by_distance(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    library = library_repo.create(
        name="retrieval-test",
        description=None,
        embedding_provider="voyage",
        embedding_model="voyage-3",
        chunk_size=800,
        chunk_overlap=100,
    )
    db_session.commit()

    near = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    far = [0.0] * (EMBEDDING_DIM - 1) + [1.0]

    document = Document(
        library_id=library.id,
        source_filename="notes.md",
        file_type="md",
        content_hash="abc",
        status="completed",
    )
    db_session.add(document)
    db_session.flush()

    chunk_repo.bulk_create(
        document.id,
        library.id,
        [(0, "closest chunk", near), (1, "farthest chunk", far)],
    )
    db_session.commit()

    service = RetrievalService(library_repo, chunk_repo)
    with patch(
        "app.application.retrieval_service.EmbeddingProviderRegistry.resolve",
        return_value=_fake_provider(near),
    ):
        results = service.query(library.id, "find the closest chunk", top_k=2)

    assert [chunk.content for chunk in results] == ["closest chunk", "farthest chunk"]


def test_query_missing_library_raises_not_found(db_session):
    library_repo = LibraryRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    service = RetrievalService(library_repo, chunk_repo)

    with pytest.raises(NotFoundError):
        service.query("00000000-0000-0000-0000-000000000000", "hello", top_k=5)
