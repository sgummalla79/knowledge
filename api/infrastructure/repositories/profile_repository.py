from uuid import UUID

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import Profile as ProfileEntity
from api.domain.errors import ConflictError
from api.infrastructure.orm import Profile as ProfileModel
from api.infrastructure.orm.profile_permission import ProfilePermission as ProfilePermissionModel


def _to_entity(model: ProfileModel) -> ProfileEntity:
    return ProfileEntity(
        id=model.id,
        org_id=model.org_id,
        name=model.name,
        description=model.description,
        is_admin=model.is_admin,
        is_system=model.is_system,
        created_by=model.created_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
    )


class ProfileRepository:
    def __init__(self, session):
        self._session = session

    def create(self, org_id: UUID, name: str, *, is_admin: bool = False, is_system: bool = False, **fields) -> ProfileEntity:
        model = ProfileModel(org_id=org_id, name=name, is_admin=is_admin, is_system=is_system, **fields)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.PROFILE_NAME_TAKEN,
                f"A profile named '{name}' already exists in this organization.",
                field="name",
            )
        return _to_entity(model)

    def get(self, profile_id: UUID) -> ProfileEntity | None:
        model = self._session.get(ProfileModel, profile_id)
        return _to_entity(model) if model is not None else None

    def get_admin_profile(self, org_id: UUID) -> ProfileEntity | None:
        model = (
            self._session.query(ProfileModel)
            .filter(ProfileModel.org_id == org_id, ProfileModel.is_admin.is_(True))
            .first()
        )
        return _to_entity(model) if model is not None else None

    def get_by_name(self, org_id: UUID, name: str) -> ProfileEntity | None:
        model = (
            self._session.query(ProfileModel).filter(ProfileModel.org_id == org_id, ProfileModel.name == name).first()
        )
        return _to_entity(model) if model is not None else None

    def list_by_org(self, org_id: UUID) -> list[ProfileEntity]:
        models = self._session.query(ProfileModel).filter(ProfileModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def update(self, profile_id: UUID, name: str, description: str | None) -> ProfileEntity:
        model = self._session.get(ProfileModel, profile_id)
        model.name = name
        model.description = description
        self._session.flush()
        return _to_entity(model)

    def delete(self, profile_id: UUID) -> None:
        model = self._session.get(ProfileModel, profile_id)
        if model is None:
            return
        self._session.delete(model)
        try:
            self._session.flush()
        except IntegrityError:
            # org_members.profile_id has no ON DELETE — a profile still assigned to any member
            # can't be removed out from under them.
            self._session.rollback()
            raise ConflictError(
                error_codes.PROFILE_IN_USE,
                "This profile is still assigned to one or more members and can't be deleted.",
            )

    def set_permissions(self, profile_id: UUID, permissions: list[str], granted_by: UUID | None) -> None:
        self._session.query(ProfilePermissionModel).filter(
            ProfilePermissionModel.profile_id == profile_id
        ).delete()
        for permission in permissions:
            self._session.add(
                ProfilePermissionModel(profile_id=profile_id, permission=permission, granted_by=granted_by)
            )
        self._session.flush()

    def list_permissions(self, profile_id: UUID) -> list[str]:
        rows = (
            self._session.query(ProfilePermissionModel.permission)
            .filter(ProfilePermissionModel.profile_id == profile_id)
            .all()
        )
        return [row[0] for row in rows]
