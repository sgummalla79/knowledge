from unittest.mock import MagicMock, patch

import pytest

from api.application.category_service import CategoryService
from api.application.ingestion_service import IngestionService
from api.application.shelf_service import ShelfService
from api.constants import EMBEDDING_DIM, DEFAULT_ADMIN_PASSWORD
from api.domain.errors import AuthenticationError, ValidationError
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.chunk_repository import ChunkRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.embedding_settings_repository import EmbeddingSettingsRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.infrastructure.storage.upload_storage import UploadStorage
from api.tests.integration.conftest import seed_active_embedding_provider

# Real-DB coverage: confirms cascade=True actually deletes documents AND their chunks (the DB's
# own ON DELETE CASCADE on chunks.document_id), verified via a real password hash/verify_password
# round trip (DEFAULT_ADMIN_PASSWORD, the same credential bootstrap_default_identity seeds) rather
# than a mocked one -- the exact wiring a unit test with a mocked identity repo can't prove.


@pytest.fixture
def storage(tmp_path):
    return UploadStorage(tmp_path)


def _ingest_document(db_session, storage, org_id, owner_id, filename="notes.txt", **create_kwargs):
    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    ingestion_service = IngestionService(document_repo, chunk_repo, EmbeddingSettingsRepository(db_session), storage)
    source_path = f"src/{filename}"
    storage.save_bytes(source_path, ("hello world " * 30).encode())
    provider = MagicMock()
    provider.embed_documents.side_effect = lambda texts, should_cancel=None: [[0.0] * EMBEDDING_DIM for _ in texts]
    with patch("api.application.ingestion_service.EmbeddingProviderRegistry.resolve", return_value=provider):
        document = ingestion_service.ingest(org_id, owner_id, filename, source_path, **create_kwargs)
    db_session.commit()
    return document


def test_category_cascade_delete_removes_documents_and_chunks(db_session, storage):
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    category_repo = CategoryRepository(db_session)
    category = category_repo.create(org_id, name="Guides", slug="guides", description=None)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    document = _ingest_document(db_session, storage, org_id, owner.id, category_id=category.id)
    assert document.category_id == category.id
    assert chunk_repo.count_for_document(document.id) > 0

    service = CategoryService(category_repo, MagicMock(), document_repo, IdentityRepository(db_session))
    deleted_count = service.delete_category(
        org_id, category.id, owner.id, cascade=True, current_password=DEFAULT_ADMIN_PASSWORD
    )
    db_session.commit()

    assert deleted_count == 1
    assert category_repo.get(category.id) is None
    assert document_repo.get(document.id) is None
    assert chunk_repo.count_for_document(document.id) == 0


def test_category_plain_delete_only_uncategorizes_documents(db_session, storage):
    """Control case: cascade=False (the default) must behave exactly as before -- the document
    survives, just uncategorized."""
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    category_repo = CategoryRepository(db_session)
    category = category_repo.create(org_id, name="Guides", slug="guides", description=None)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    document = _ingest_document(db_session, storage, org_id, owner.id, category_id=category.id)

    service = CategoryService(category_repo, MagicMock(), document_repo, IdentityRepository(db_session))
    deleted_count = service.delete_category(org_id, category.id, owner.id, cascade=False)
    db_session.commit()

    assert deleted_count == 0
    assert category_repo.get(category.id) is None
    survivor = document_repo.get(document.id)
    assert survivor is not None
    assert survivor.category_id is None


def test_category_cascade_delete_wrong_password_leaves_everything_intact(db_session, storage):
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    category_repo = CategoryRepository(db_session)
    category = category_repo.create(org_id, name="Guides", slug="guides", description=None)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    document = _ingest_document(db_session, storage, org_id, owner.id, category_id=category.id)

    service = CategoryService(category_repo, MagicMock(), document_repo, IdentityRepository(db_session))
    with pytest.raises(AuthenticationError):
        service.delete_category(org_id, category.id, owner.id, cascade=True, current_password="definitely-wrong")
    db_session.commit()

    assert category_repo.get(category.id) is not None
    assert document_repo.get(document.id) is not None


def test_shelf_cascade_delete_removes_documents_and_chunks(db_session, storage):
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    shelf_repo = ShelfRepository(db_session)
    shelf = shelf_repo.create(org_id, name="Engineering", slug="engineering", description=None)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    document = _ingest_document(db_session, storage, org_id, owner.id)
    shelf_repo.add_document(document.id, shelf.id)
    db_session.commit()

    service = ShelfService(shelf_repo, document_repo, IdentityRepository(db_session))
    deleted_count = service.delete_shelf(
        org_id, shelf.id, owner.id, cascade=True, current_password=DEFAULT_ADMIN_PASSWORD
    )
    db_session.commit()

    assert deleted_count == 1
    assert shelf_repo.get(shelf.id) is None
    assert document_repo.get(document.id) is None
    assert chunk_repo.count_for_document(document.id) == 0


def test_shelf_plain_delete_only_removes_shelf_assignment(db_session, storage):
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    shelf_repo = ShelfRepository(db_session)
    shelf = shelf_repo.create(org_id, name="Engineering", slug="engineering", description=None)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    document = _ingest_document(db_session, storage, org_id, owner.id)
    shelf_repo.add_document(document.id, shelf.id)
    db_session.commit()

    service = ShelfService(shelf_repo, document_repo, IdentityRepository(db_session))
    deleted_count = service.delete_shelf(org_id, shelf.id, owner.id, cascade=False)
    db_session.commit()

    assert deleted_count == 0
    assert shelf_repo.get(shelf.id) is None
    assert document_repo.get(document.id) is not None


def test_shelf_cascade_delete_default_shelf_raises_without_deleting_anything(db_session, storage):
    bootstrap_default_identity(db_session)
    owner = IdentityRepository(db_session).get()
    org_id = seed_active_embedding_provider(
        db_session, "voyage", "voyage-3", "test-key", dimensions=EMBEDDING_DIM, chunk_size=20, chunk_overlap=5
    )
    shelf_repo = ShelfRepository(db_session)
    default_shelf = shelf_repo.create(org_id, name="Default", slug="default", description=None, is_default=True)
    db_session.commit()

    document_repo = DocumentRepository(db_session)
    document = _ingest_document(db_session, storage, org_id, owner.id)
    shelf_repo.add_document(document.id, default_shelf.id)
    db_session.commit()

    service = ShelfService(shelf_repo, document_repo, IdentityRepository(db_session))
    with pytest.raises(ValidationError):
        service.delete_shelf(org_id, default_shelf.id, owner.id, cascade=True, current_password=DEFAULT_ADMIN_PASSWORD)
    db_session.commit()

    assert shelf_repo.get(default_shelf.id) is not None
    assert document_repo.get(document.id) is not None
