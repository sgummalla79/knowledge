from datetime import datetime, timezone
from uuid import UUID

from api.domain.entities import AuthorizationCode as AuthorizationCodeEntity
from api.infrastructure.orm.authorization_code import AuthorizationCode as AuthorizationCodeModel


def _to_entity(model: AuthorizationCodeModel) -> AuthorizationCodeEntity:
    return AuthorizationCodeEntity(
        id=model.id,
        code_hash=model.code_hash,
        application_id=model.application_id,
        org_id=model.org_id,
        identity_id=model.identity_id,
        redirect_uri=model.redirect_uri,
        code_challenge=model.code_challenge,
        code_challenge_method=model.code_challenge_method,
        scope=model.scope,
        expires_at=model.expires_at,
        consumed_at=model.consumed_at,
        created_at=model.created_at,
    )


class AuthorizationCodeRepository:
    def __init__(self, session):
        self._session = session

    def create(self, application_id: UUID, org_id: UUID, identity_id: UUID, **fields) -> AuthorizationCodeEntity:
        model = AuthorizationCodeModel(application_id=application_id, org_id=org_id, identity_id=identity_id, **fields)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get_by_code_hash(self, code_hash: str) -> AuthorizationCodeEntity | None:
        model = self._session.query(AuthorizationCodeModel).filter(AuthorizationCodeModel.code_hash == code_hash).first()
        return _to_entity(model) if model is not None else None

    def mark_consumed(self, authorization_code_id: UUID) -> None:
        model = self._session.get(AuthorizationCodeModel, authorization_code_id)
        if model is not None:
            model.consumed_at = datetime.now(timezone.utc)
            self._session.flush()
