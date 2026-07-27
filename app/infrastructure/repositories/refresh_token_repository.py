from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_

from app.domain.entities import RefreshToken as RefreshTokenEntity
from app.infrastructure.orm import RefreshToken as RefreshTokenModel


def _to_entity(model: RefreshTokenModel) -> RefreshTokenEntity:
    return RefreshTokenEntity(
        id=model.id,
        application_id=model.application_id,
        scope=model.scope.split(),
        created_at=model.created_at,
        expires_at=model.expires_at,
        last_used_at=model.last_used_at,
        revoked_at=model.revoked_at,
    )


class RefreshTokenRepository:
    def __init__(self, session):
        self._session = session

    def create(self, application_id: UUID, token_hash: str, scope: list[str], expires_at) -> RefreshTokenEntity:
        model = RefreshTokenModel(
            application_id=application_id,
            token_hash=token_hash,
            scope=" ".join(scope),
            expires_at=expires_at,
        )
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def find_valid_by_hash(self, token_hash: str) -> RefreshTokenEntity | None:
        now = datetime.now(timezone.utc)
        model = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.token_hash == token_hash)
            .filter(RefreshTokenModel.revoked_at.is_(None))
            .filter(or_(RefreshTokenModel.expires_at.is_(None), RefreshTokenModel.expires_at > now))
            .first()
        )
        return _to_entity(model) if model is not None else None

    def find_current_for_application(self, application_id: UUID) -> RefreshTokenEntity | None:
        model = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.application_id == application_id)
            .filter(RefreshTokenModel.revoked_at.is_(None))
            .order_by(RefreshTokenModel.created_at.desc())
            .first()
        )
        return _to_entity(model) if model is not None else None

    def revoke(self, token_id: UUID) -> None:
        model = self._session.query(RefreshTokenModel).filter(RefreshTokenModel.id == token_id).first()
        if model is not None:
            model.revoked_at = datetime.now(timezone.utc)
            self._session.flush()

    def touch_last_used(self, token_id: UUID) -> None:
        model = self._session.query(RefreshTokenModel).filter(RefreshTokenModel.id == token_id).one()
        model.last_used_at = datetime.now(timezone.utc)
        self._session.flush()
