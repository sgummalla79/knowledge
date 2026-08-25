from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.application.shelf_service import ShelfService
from api.domain import error_codes
from api.domain.entities import Shelf
from api.domain.errors import AuthenticationError, ValidationError

# Unit coverage for delete_shelf's cascade path specifically -- mirrors
# test_category_service.py's own cascade-delete coverage. Every other ShelfService method is
# already covered at the route layer (test_shelf_routes.py, ShelfService mocked there) plus real
# DB behavior for the rest of this repository's surface.


def _shelf(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(), org_id=uuid4(), name="Engineering", slug="engineering", description=None,
        is_default=False, created_by=None, last_modified_by=None, created_at=now, last_modified_at=now,
    )
    fields.update(overrides)
    return Shelf(**fields)


def test_delete_shelf_default_shelf_raises_without_touching_documents():
    org_id = uuid4()
    shelf = _shelf(org_id=org_id, is_default=True)
    repository = MagicMock()
    repository.get.return_value = shelf
    document_repo = MagicMock()
    service = ShelfService(repository, document_repo, MagicMock())

    with pytest.raises(ValidationError) as exc_info:
        service.delete_shelf(org_id, shelf.id, cascade=True, current_password="whatever")

    assert exc_info.value.code == error_codes.DEFAULT_SHELF_NOT_DELETABLE
    document_repo.count_for_org.assert_not_called()
    repository.delete.assert_not_called()


def test_delete_shelf_non_cascade_never_touches_documents():
    org_id = uuid4()
    shelf = _shelf(org_id=org_id)
    repository = MagicMock()
    repository.get.return_value = shelf
    document_repo = MagicMock()
    service = ShelfService(repository, document_repo, MagicMock())

    result = service.delete_shelf(org_id, shelf.id, cascade=False)

    document_repo.count_for_org.assert_not_called()
    document_repo.delete.assert_not_called()
    repository.delete.assert_called_once_with(shelf.id)
    assert result == 0


def test_delete_shelf_cascade_without_password_raises_validation_error():
    org_id = uuid4()
    shelf = _shelf(org_id=org_id)
    repository = MagicMock()
    repository.get.return_value = shelf
    service = ShelfService(repository, MagicMock(), MagicMock())

    with pytest.raises(ValidationError) as exc_info:
        service.delete_shelf(org_id, shelf.id, uuid4(), cascade=True, current_password=None)

    assert exc_info.value.field == "current_password"
    repository.delete.assert_not_called()


def test_delete_shelf_cascade_with_wrong_password_raises_authentication_error():
    org_id = uuid4()
    shelf = _shelf(org_id=org_id)
    repository = MagicMock()
    repository.get.return_value = shelf
    identity_repo = MagicMock()
    identity_repo.get_by_id.return_value = MagicMock(password_hash="hashed")
    service = ShelfService(repository, MagicMock(), identity_repo)

    with patch("api.application.shelf_service.verify_password", return_value=False):
        with pytest.raises(AuthenticationError) as exc_info:
            service.delete_shelf(org_id, shelf.id, uuid4(), cascade=True, current_password="wrong")

    # Distinct from the generic UNAUTHORIZED code -- see webui/src/api/client.ts's own note on
    # why this matters (a wrong password here must not force a sign-out/redirect).
    assert exc_info.value.code == error_codes.INCORRECT_PASSWORD

    repository.delete.assert_not_called()


def test_delete_shelf_cascade_deletes_every_document_on_the_shelf_then_the_shelf():
    org_id = uuid4()
    shelf = _shelf(org_id=org_id)
    acting_identity_id = uuid4()
    repository = MagicMock()
    repository.get.return_value = shelf
    identity_repo = MagicMock()
    identity_repo.get_by_id.return_value = MagicMock(password_hash="hashed")
    document_repo = MagicMock()
    document_repo.count_for_org.return_value = 2
    doc_a, doc_b = MagicMock(id=uuid4()), MagicMock(id=uuid4())
    document_repo.list_for_org.return_value = [doc_a, doc_b]
    service = ShelfService(repository, document_repo, identity_repo)

    with patch("api.application.shelf_service.verify_password", return_value=True):
        deleted_count = service.delete_shelf(org_id, shelf.id, acting_identity_id, cascade=True, current_password="correct")

    document_repo.count_for_org.assert_called_once_with(org_id, shelf_id=shelf.id)
    document_repo.list_for_org.assert_called_once_with(org_id, 2, 0, "created_at", shelf_id=shelf.id)
    assert document_repo.delete.call_args_list == [((doc_a.id,),), ((doc_b.id,),)]
    repository.delete.assert_called_once_with(shelf.id)
    assert deleted_count == 2


def test_delete_shelf_cascade_with_no_documents_skips_document_lookup():
    org_id = uuid4()
    shelf = _shelf(org_id=org_id)
    repository = MagicMock()
    repository.get.return_value = shelf
    identity_repo = MagicMock()
    identity_repo.get_by_id.return_value = MagicMock(password_hash="hashed")
    document_repo = MagicMock()
    document_repo.count_for_org.return_value = 0
    service = ShelfService(repository, document_repo, identity_repo)

    with patch("api.application.shelf_service.verify_password", return_value=True):
        deleted_count = service.delete_shelf(org_id, shelf.id, uuid4(), cascade=True, current_password="correct")

    document_repo.list_for_org.assert_not_called()
    assert deleted_count == 0
