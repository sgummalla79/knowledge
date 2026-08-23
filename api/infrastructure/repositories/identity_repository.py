from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import Identity as IdentityEntity
from api.domain.errors import ConflictError
from api.infrastructure.orm import Identity as IdentityModel


def _to_entity(model: IdentityModel) -> IdentityEntity:
    return IdentityEntity(
        id=model.id,
        username=model.username,
        email=model.email,
        name=model.name,
        password_hash=model.password_hash,
        must_change_password=model.must_change_password,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
        last_active_at=model.last_active_at,
    )


class IdentityRepository:
    """`get()` is kept as a zero-arg "first identity in the table" lookup — used by
    bootstrap/tests that only ever care about the one seeded identity."""

    def __init__(self, session):
        self._session = session

    def get(self) -> IdentityEntity | None:
        model = self._session.query(IdentityModel).first()
        return _to_entity(model) if model is not None else None

    def get_by_id(self, identity_id: UUID) -> IdentityEntity | None:
        model = self._session.get(IdentityModel, identity_id)
        return _to_entity(model) if model is not None else None

    def get_by_username(self, username: str) -> IdentityEntity | None:
        model = self._session.query(IdentityModel).filter(IdentityModel.username == username).first()
        return _to_entity(model) if model is not None else None

    def create(
        self,
        username: str,
        password_hash: str,
        *,
        name: str,
        email: str | None = None,
        must_change_password: bool = True,
    ) -> IdentityEntity:
        model = IdentityModel(
            username=username,
            email=email,
            name=name,
            password_hash=password_hash,
            must_change_password=must_change_password,
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.IDENTITY_USERNAME_TAKEN,
                f"An account with username '{username}' already exists.",
                field="username",
            )
        return _to_entity(model)

    def update_password(self, identity_id: UUID, password_hash: str) -> None:
        model = self._session.query(IdentityModel).filter(IdentityModel.id == identity_id).one()
        model.password_hash = password_hash
        model.must_change_password = False
        self._session.flush()

    def update_profile(self, identity_id: UUID, *, name: str, email: str) -> IdentityEntity:
        model = self._session.query(IdentityModel).filter(IdentityModel.id == identity_id).one()
        model.name = name
        model.email = email
        self._session.flush()
        return _to_entity(model)

    def update_username(self, identity_id: UUID, username: str) -> IdentityEntity:
        model = self._session.query(IdentityModel).filter(IdentityModel.id == identity_id).one()
        model.username = username
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.IDENTITY_USERNAME_TAKEN,
                f"An account with username '{username}' already exists.",
                field="username",
            )
        return _to_entity(model)

    def get_last_active_at(self, identity_id: UUID) -> datetime | None:
        """Narrow, single-purpose read for api/presentation/web/session_guard.py's inactivity
        check — deliberately not routed through get_by_id/the full Identity entity, so a
        nonexistent identity_id (e.g. a test's fake session, never seeded in the DB) returns
        plain None rather than requiring a full fake entity, and None is already the correct
        "never checked before, don't reject" behavior either way."""
        model = self._session.get(IdentityModel, identity_id)
        return model.last_active_at if model is not None else None

    def touch_last_active(self, identity_id: UUID) -> None:
        model = self._session.get(IdentityModel, identity_id)
        if model is not None:
            model.last_active_at = datetime.now(timezone.utc)
            self._session.flush()
