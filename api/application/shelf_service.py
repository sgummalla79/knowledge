import logging
from uuid import UUID

from api.application.slugify import slugify
from api.domain import error_codes
from api.domain.entities import Shelf
from api.domain.errors import AuthenticationError, NotFoundError, ValidationError
from api.domain.ports import DocumentRepositoryPort, IdentityRepositoryPort, ShelfRepositoryPort
from api.infrastructure.auth.passwords import verify_password

logger = logging.getLogger(__name__)


class ShelfService:
    def __init__(
        self,
        repository: ShelfRepositoryPort,
        document_repo: DocumentRepositoryPort | None = None,
        identity_repo: IdentityRepositoryPort | None = None,
    ):
        self._repository = repository
        # Optional: only delete_shelf(cascade=True) needs these -- see its own docstring.
        self._documents = document_repo
        self._identities = identity_repo

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

    def delete_shelf(
        self,
        org_id: UUID,
        shelf_id: UUID,
        acting_identity_id: UUID | None = None,
        cascade: bool = False,
        current_password: str | None = None,
    ) -> int:
        """Default (cascade=False) is a plain unlink, exactly as before -- documents on this shelf
        just lose that shelf assignment (document_shelves.shelf_id ON DELETE CASCADE removes the
        association rows only). cascade=True additionally, permanently deletes every document
        that was on this shelf; their chunks cascade-delete at the DB level, same as
        CategoryService.delete_category's own cascade path -- see that method's docstring for the
        full password-reverification rationale. Returns how many documents were deleted (0 for a
        plain unlink)."""
        shelf = self.get_shelf(org_id, shelf_id)
        if shelf.is_default:
            raise ValidationError(
                error_codes.DEFAULT_SHELF_NOT_DELETABLE,
                "The default shelf can't be deleted — every document needs at least one shelf.",
                field="shelf_id",
            )

        deleted_count = 0
        if cascade:
            if not current_password:
                raise ValidationError(
                    error_codes.VALIDATION_ERROR,
                    "Current password is required to permanently delete documents.",
                    field="current_password",
                )
            identity = self._identities.get_by_id(acting_identity_id) if acting_identity_id else None
            if identity is None or not verify_password(current_password, identity.password_hash):
                raise AuthenticationError("Incorrect password.", code=error_codes.INCORRECT_PASSWORD)

            deleted_count = self._documents.count_for_org(org_id, shelf_id=shelf_id)
            if deleted_count:
                documents = self._documents.list_for_org(org_id, deleted_count, 0, "created_at", shelf_id=shelf_id)
                for document in documents:
                    self._documents.delete(document.id)

        self._repository.delete(shelf_id)
        logger.info(
            "Shelf deleted",
            extra={
                "org_id": str(org_id),
                "shelf_id": str(shelf_id),
                "cascade": cascade,
                "documents_deleted": deleted_count,
            },
        )
        return deleted_count

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

    def list_accessible_shelves(self, user_id: UUID) -> list[Shelf]:
        shelf_ids = self._repository.list_accessible_shelf_ids(user_id)
        shelves = (self._repository.get(shelf_id) for shelf_id in shelf_ids)
        return [shelf for shelf in shelves if shelf is not None]

    def document_count(self, shelf_id: UUID) -> int:
        return self._repository.count_documents(shelf_id)

    def member_count(self, shelf_id: UUID) -> int:
        return self._repository.count_members(shelf_id)
