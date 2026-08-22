from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import Organization as OrganizationEntity
from api.domain.errors import ConflictError
from api.infrastructure.orm import Organization as OrganizationModel


def _to_entity(model: OrganizationModel) -> OrganizationEntity:
    return OrganizationEntity(
        id=model.id,
        name=model.name,
        slug=model.slug,
        description=model.description,
        plan=model.plan,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
    )


class OrganizationRepository:
    def __init__(self, session):
        self._session = session

    def create(self, name: str, slug: str, **fields) -> OrganizationEntity:
        model = OrganizationModel(name=name, slug=slug, **fields)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.ORGANIZATION_SLUG_TAKEN,
                f"An organization with slug '{slug}' already exists.",
                field="slug",
            )
        return _to_entity(model)

    def get(self, org_id) -> OrganizationEntity | None:
        model = self._session.get(OrganizationModel, org_id)
        return _to_entity(model) if model is not None else None

    def get_by_slug(self, slug: str) -> OrganizationEntity | None:
        model = self._session.query(OrganizationModel).filter(OrganizationModel.slug == slug).first()
        return _to_entity(model) if model is not None else None

    def list(self) -> list[OrganizationEntity]:
        models = self._session.query(OrganizationModel).all()
        return [_to_entity(model) for model in models]
