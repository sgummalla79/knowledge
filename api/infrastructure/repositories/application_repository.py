from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import Application as ApplicationEntity
from api.domain.errors import ConflictError
from api.infrastructure.orm import Application as ApplicationModel


def _to_entity(model: ApplicationModel) -> ApplicationEntity:
    return ApplicationEntity(
        id=model.id,
        org_id=model.org_id,
        name=model.name,
        description=model.description,
        auth_method=model.auth_method,
        status=model.status,
        service_identity_id=model.service_identity_id,
        execute_as_identity_id=model.execute_as_identity_id,
        mcp_access=model.mcp_access,
        api_access=model.api_access,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        revoked_at=model.revoked_at,
        revoked_by=model.revoked_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
    )


class ApplicationRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, name: str, auth_method: str, service_identity_id: UUID, **fields) -> ApplicationEntity:
        model = ApplicationModel(
            org_id=org_id, name=name, auth_method=auth_method, service_identity_id=service_identity_id, **fields
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.APPLICATION_NAME_TAKEN,
                f"An application named '{name}' already exists in this organization.",
                field="name",
            )
        return _to_entity(model)

    def get(self, application_id: UUID) -> ApplicationEntity | None:
        model = self._session.get(ApplicationModel, application_id)
        return _to_entity(model) if model is not None else None

    def list_by_org(self, org_id: UUID) -> list[ApplicationEntity]:
        models = self._session.query(ApplicationModel).filter(ApplicationModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def update(self, application_id: UUID, name: str, description: str | None) -> ApplicationEntity:
        model = self._session.get(ApplicationModel, application_id)
        model.name = name
        model.description = description
        self._session.flush()
        return _to_entity(model)

    def revoke(self, application_id: UUID, revoked_by: UUID) -> ApplicationEntity:
        model = self._session.get(ApplicationModel, application_id)
        model.status = "revoked"
        model.revoked_at = datetime.now(timezone.utc)
        model.revoked_by = revoked_by
        self._session.flush()
        return _to_entity(model)

    def delete(self, application_id: UUID) -> None:
        model = self._session.get(ApplicationModel, application_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
