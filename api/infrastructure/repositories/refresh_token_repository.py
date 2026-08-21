from datetime import datetime, timezone
from uuid import UUID

from api.domain.entities import RefreshToken as RefreshTokenEntity
from api.infrastructure.orm.refresh_token import RefreshToken as RefreshTokenModel


def _to_entity(model: RefreshTokenModel) -> RefreshTokenEntity:
    return RefreshTokenEntity(
        id=model.id,
        token_hash=model.token_hash,
        application_id=model.application_id,
        org_id=model.org_id,
        identity_id=model.identity_id,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
    )


class RefreshTokenRepository:
    def __init__(self, session):
        self._session = session

    def create(self, application_id: UUID, org_id: UUID, identity_id: UUID, token_hash: str, expires_at) -> RefreshTokenEntity:
        model = RefreshTokenModel(
            application_id=application_id,
            org_id=org_id,
            identity_id=identity_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get_by_token_hash(self, token_hash: str) -> RefreshTokenEntity | None:
        model = self._session.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).first()
        return _to_entity(model) if model is not None else None

    def touch_last_used(self, refresh_token_id: UUID) -> None:
        model = self._session.get(RefreshTokenModel, refresh_token_id)
        if model is not None:
            model.last_used_at = datetime.now(timezone.utc)
            self._session.flush()
