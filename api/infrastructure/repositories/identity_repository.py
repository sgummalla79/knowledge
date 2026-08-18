from uuid import UUID

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import Identity as IdentityEntity
from api.domain.errors import ConflictError
from api.infrastructure.orm import Identity as IdentityModel


def _to_entity(model: IdentityModel) -> IdentityEntity:
    return IdentityEntity(
        id=model.id,
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

    def get_by_email(self, email: str) -> IdentityEntity | None:
        model = self._session.query(IdentityModel).filter(IdentityModel.email == email).first()
        return _to_entity(model) if model is not None else None

    def create(self, email: str, password_hash: str, *, name: str, must_change_password: bool = True) -> IdentityEntity:
        model = IdentityModel(
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
                error_codes.IDENTITY_EMAIL_TAKEN,
                f"An account with email '{email}' already exists.",
                field="email",
            )
        return _to_entity(model)

    def update_password(self, identity_id: UUID, password_hash: str) -> None:
        model = self._session.query(IdentityModel).filter(IdentityModel.id == identity_id).one()
        model.password_hash = password_hash
        model.must_change_password = False
        self._session.flush()
