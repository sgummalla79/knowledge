from uuid import UUID

from app.domain.entities import User as UserEntity
from app.infrastructure.orm import User as UserModel


def _to_entity(model: UserModel) -> UserEntity:
    return UserEntity(
        id=model.id,
        org_id=model.org_id,
        email=model.email,
        name=model.name,
        role=model.role,
        password_hash=model.password_hash,
        must_change_password=model.must_change_password,
        invited_by=model.invited_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
        last_active_at=model.last_active_at,
    )


class UserRepository:
    """Users now belong to an organization (see migration 0018), but `get()` is kept as a
    zero-arg "first user in the table" lookup for backward compatibility with the still-untouched
    single-admin application/route layer (Phase B/C of the multi-tenant migration) — it is no
    longer a meaningful "the one user" query once multiple orgs/users exist, only a transitional
    shim."""

    def __init__(self, session):
        self._session = session

    def get(self) -> UserEntity | None:
        model = self._session.query(UserModel).first()
        return _to_entity(model) if model is not None else None

    def get_by_id(self, user_id: UUID) -> UserEntity | None:
        model = self._session.get(UserModel, user_id)
        return _to_entity(model) if model is not None else None

    def get_by_org(self, org_id: UUID) -> list[UserEntity]:
        models = self._session.query(UserModel).filter(UserModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def get_by_email(self, org_id: UUID, email: str) -> UserEntity | None:
        model = (
            self._session.query(UserModel)
            .filter(UserModel.org_id == org_id, UserModel.email == email)
            .first()
        )
        return _to_entity(model) if model is not None else None

    def create_default(self, email: str, password_hash: str, *, org_id: UUID, name: str) -> UserEntity:
        model = UserModel(
            org_id=org_id,
            email=email,
            name=name,
            role="admin",
            password_hash=password_hash,
            must_change_password=True,
        )
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def update_password(self, user_id: UUID, password_hash: str) -> None:
        model = self._session.query(UserModel).filter(UserModel.id == user_id).one()
        model.password_hash = password_hash
        model.must_change_password = False
        self._session.flush()
