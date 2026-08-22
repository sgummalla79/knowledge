from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import Shelf as ShelfEntity
from api.domain.errors import ConflictError
from api.infrastructure.orm import DocumentShelf as DocumentShelfModel
from api.infrastructure.orm import Shelf as ShelfModel
from api.infrastructure.orm import UserShelfAccess as UserShelfAccessModel


def _to_entity(model: ShelfModel) -> ShelfEntity:
    return ShelfEntity(
        id=model.id,
        org_id=model.org_id,
        name=model.name,
        slug=model.slug,
        description=model.description,
        is_default=model.is_default,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
    )


class ShelfRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, name: str, slug: str, **fields) -> ShelfEntity:
        model = ShelfModel(org_id=org_id, name=name, slug=slug, **fields)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.SHELF_SLUG_TAKEN,
                f"A shelf with slug '{slug}' already exists in this organization.",
                field="slug",
            )
        return _to_entity(model)

    def get(self, shelf_id: UUID) -> ShelfEntity | None:
        model = self._session.get(ShelfModel, shelf_id)
        return _to_entity(model) if model is not None else None

    def update(self, shelf_id: UUID, name: str, description: str | None) -> ShelfEntity:
        model = self._session.get(ShelfModel, shelf_id)
        model.name = name
        model.description = description
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.SHELF_SLUG_TAKEN,
                f"A shelf named '{name}' already exists in this organization.",
                field="name",
            )
        return _to_entity(model)

    def delete(self, shelf_id: UUID) -> None:
        model = self._session.get(ShelfModel, shelf_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def count_documents(self, shelf_id: UUID) -> int:
        return (
            self._session.query(DocumentShelfModel).filter(DocumentShelfModel.shelf_id == shelf_id).count()
        )

    def count_members(self, shelf_id: UUID) -> int:
        return (
            self._session.query(UserShelfAccessModel)
            .filter(UserShelfAccessModel.shelf_id == shelf_id)
            .count()
        )

    def list_by_org(self, org_id: UUID) -> list[ShelfEntity]:
        models = self._session.query(ShelfModel).filter(ShelfModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def get_default_for_org(self, org_id: UUID) -> ShelfEntity | None:
        model = (
            self._session.query(ShelfModel)
            .filter(ShelfModel.org_id == org_id, ShelfModel.is_default.is_(True))
            .first()
        )
        return _to_entity(model) if model is not None else None

    def add_document(self, document_id: UUID, shelf_id: UUID) -> None:
        exists = (
            self._session.query(DocumentShelfModel)
            .filter(DocumentShelfModel.document_id == document_id, DocumentShelfModel.shelf_id == shelf_id)
            .first()
        )
        if exists is None:
            self._session.add(DocumentShelfModel(document_id=document_id, shelf_id=shelf_id))
            self._session.flush()

    def remove_document(self, document_id: UUID, shelf_id: UUID) -> None:
        self._session.query(DocumentShelfModel).filter(
            DocumentShelfModel.document_id == document_id, DocumentShelfModel.shelf_id == shelf_id
        ).delete()
        self._session.flush()

    def list_shelves_for_document(self, document_id: UUID) -> list[ShelfEntity]:
        models = (
            self._session.query(ShelfModel)
            .join(DocumentShelfModel, DocumentShelfModel.shelf_id == ShelfModel.id)
            .filter(DocumentShelfModel.document_id == document_id)
            .all()
        )
        return [_to_entity(model) for model in models]

    def grant_user_access(self, user_id: UUID, shelf_id: UUID, granted_by: UUID | None) -> None:
        exists = (
            self._session.query(UserShelfAccessModel)
            .filter(UserShelfAccessModel.user_id == user_id, UserShelfAccessModel.shelf_id == shelf_id)
            .first()
        )
        if exists is None:
            self._session.add(UserShelfAccessModel(user_id=user_id, shelf_id=shelf_id, granted_by=granted_by))
            self._session.flush()

    def revoke_user_access(self, user_id: UUID, shelf_id: UUID) -> None:
        self._session.query(UserShelfAccessModel).filter(
            UserShelfAccessModel.user_id == user_id, UserShelfAccessModel.shelf_id == shelf_id
        ).delete()
        self._session.flush()

    def list_accessible_shelf_ids(self, user_id: UUID) -> list[UUID]:
        rows = (
            self._session.query(UserShelfAccessModel.shelf_id)
            .filter(UserShelfAccessModel.user_id == user_id)
            .all()
        )
        return [row.shelf_id for row in rows]
