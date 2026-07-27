from uuid import UUID

from app.domain.entities import User as UserEntity
from app.infrastructure.orm import User as UserModel


def _to_entity(model: UserModel) -> UserEntity:
    return UserEntity(
        id=model.id,
        username=model.username,
        password_hash=model.password_hash,
        must_change_password=model.must_change_password,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class UserRepository:
    """Single admin user — application-level convention (bootstrap only inserts if empty), same
    singleton posture as EmbeddingSettingsRepository, not a DB-level constraint."""

    def __init__(self, session):
        self._session = session

    def get(self) -> UserEntity | None:
        model = self._session.query(UserModel).first()
        return _to_entity(model) if model is not None else None

    def create_default(self, username: str, password_hash: str) -> UserEntity:
        model = UserModel(username=username, password_hash=password_hash, must_change_password=True)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def update_password(self, user_id: UUID, password_hash: str) -> None:
        model = self._session.query(UserModel).filter(UserModel.id == user_id).one()
        model.password_hash = password_hash
        model.must_change_password = False
        self._session.flush()
