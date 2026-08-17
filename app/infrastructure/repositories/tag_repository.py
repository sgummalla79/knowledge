from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.domain import error_codes
from app.domain.entities import Tag as TagEntity
from app.domain.errors import ConflictError
from app.infrastructure.orm import DocumentTag as DocumentTagModel
from app.infrastructure.orm import Tag as TagModel


def _to_entity(model: TagModel) -> TagEntity:
    return TagEntity(
        id=model.id,
        org_id=model.org_id,
        name=model.name,
        created_by=model.created_by,
        created_at=model.created_at,
    )


class TagRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, name: str, **fields) -> TagEntity:
        model = TagModel(org_id=org_id, name=name, **fields)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.TAG_NAME_TAKEN,
                f"A tag named '{name}' already exists in this organization.",
                field="name",
            )
        return _to_entity(model)

    def get(self, tag_id: UUID) -> TagEntity | None:
        model = self._session.get(TagModel, tag_id)
        return _to_entity(model) if model is not None else None

    def list_by_org(self, org_id: UUID) -> list[TagEntity]:
        models = self._session.query(TagModel).filter(TagModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def tag_document(self, document_id: UUID, tag_id: UUID) -> None:
        exists = (
            self._session.query(DocumentTagModel)
            .filter(DocumentTagModel.document_id == document_id, DocumentTagModel.tag_id == tag_id)
            .first()
        )
        if exists is None:
            self._session.add(DocumentTagModel(document_id=document_id, tag_id=tag_id))
            self._session.flush()

    def untag_document(self, document_id: UUID, tag_id: UUID) -> None:
        self._session.query(DocumentTagModel).filter(
            DocumentTagModel.document_id == document_id, DocumentTagModel.tag_id == tag_id
        ).delete()
        self._session.flush()

    def list_for_document(self, document_id: UUID) -> list[TagEntity]:
        models = (
            self._session.query(TagModel)
            .join(DocumentTagModel, DocumentTagModel.tag_id == TagModel.id)
            .filter(DocumentTagModel.document_id == document_id)
            .all()
        )
        return [_to_entity(model) for model in models]
