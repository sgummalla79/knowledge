import logging
from uuid import UUID

from api.application.slugify import slugify
from api.domain import error_codes
from api.domain.entities import Shelf
from api.domain.errors import NotFoundError, ValidationError
from api.domain.ports import ShelfRepositoryPort

logger = logging.getLogger(__name__)


class ShelfService:
    def __init__(self, repository: ShelfRepositoryPort):
        self._repository = repository

    def create_shelf(self, org_id: UUID, name: str, description: str | None) -> Shelf:
        slug = slugify(name)
        return self._repository.create(org_id, name=name, slug=slug, description=description)

    def get_shelf(self, org_id: UUID, shelf_id: UUID) -> Shelf:
        shelf = self._repository.get(shelf_id)
        if shelf is None or shelf.org_id != org_id:
            raise NotFoundError(error_codes.SHELF_NOT_FOUND, "Shelf not found.")
        return shelf

    def list_shelves(self, org_id: UUID) -> list[Shelf]:
        return self._repository.list_by_org(org_id)

    def update_shelf(self, org_id: UUID, shelf_id: UUID, name: str, description: str | None) -> Shelf:
        self.get_shelf(org_id, shelf_id)
        return self._repository.update(shelf_id, name=name, description=description)

    def delete_shelf(self, org_id: UUID, shelf_id: UUID) -> None:
        shelf = self.get_shelf(org_id, shelf_id)
        if shelf.is_default:
            raise ValidationError(
                error_codes.DEFAULT_SHELF_NOT_DELETABLE,
                "The default shelf can't be deleted — every document needs at least one shelf.",
                field="shelf_id",
            )
        self._repository.delete(shelf_id)
        logger.info("Shelf deleted", extra={"org_id": str(org_id), "shelf_id": str(shelf_id)})

    def add_document(self, org_id: UUID, shelf_id: UUID, document_id: UUID) -> None:
        self.get_shelf(org_id, shelf_id)
        self._repository.add_document(document_id, shelf_id)

    def remove_document(self, org_id: UUID, shelf_id: UUID, document_id: UUID) -> None:
        self.get_shelf(org_id, shelf_id)
        self._repository.remove_document(document_id, shelf_id)

    def grant_access(self, org_id: UUID, shelf_id: UUID, user_id: UUID, granted_by: UUID | None) -> None:
        self.get_shelf(org_id, shelf_id)
        self._repository.grant_user_access(user_id, shelf_id, granted_by)

    def revoke_access(self, org_id: UUID, shelf_id: UUID, user_id: UUID) -> None:
        self.get_shelf(org_id, shelf_id)
        self._repository.revoke_user_access(user_id, shelf_id)

    def list_document_shelves(self, document_id: UUID) -> list[Shelf]:
        return self._repository.list_shelves_for_document(document_id)

    def document_count(self, shelf_id: UUID) -> int:
        return self._repository.count_documents(shelf_id)

    def member_count(self, shelf_id: UUID) -> int:
        return self._repository.count_members(shelf_id)
