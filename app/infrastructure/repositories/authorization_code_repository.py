from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import AuthorizationCode as AuthorizationCodeEntity
from app.infrastructure.orm import AuthorizationCode as AuthorizationCodeModel


def _to_entity(model: AuthorizationCodeModel) -> AuthorizationCodeEntity:
    return AuthorizationCodeEntity(
        id=model.id,
        application_id=model.application_id,
        redirect_uri=model.redirect_uri,
        code_challenge=model.code_challenge,
        code_challenge_method=model.code_challenge_method,
        scope=model.scope.split(),
        created_at=model.created_at,
        expires_at=model.expires_at,
        used_at=model.used_at,
    )


class AuthorizationCodeRepository:
    def __init__(self, session):
        self._session = session

    def create(
        self,
        application_id: UUID,
        code_hash: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: list[str],
        expires_at: datetime,
    ) -> AuthorizationCodeEntity:
        model = AuthorizationCodeModel(
            application_id=application_id,
            code_hash=code_hash,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=" ".join(scope),
            expires_at=expires_at,
        )
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def find_valid_by_hash(self, code_hash: str) -> AuthorizationCodeEntity | None:
        now = datetime.now(timezone.utc)
        model = (
            self._session.query(AuthorizationCodeModel)
            .filter(AuthorizationCodeModel.code_hash == code_hash)
            .filter(AuthorizationCodeModel.used_at.is_(None))
            .filter(AuthorizationCodeModel.expires_at > now)
            .first()
        )
        return _to_entity(model) if model is not None else None

    def mark_used(self, code_id: UUID) -> None:
        model = self._session.query(AuthorizationCodeModel).filter(AuthorizationCodeModel.id == code_id).one()
        model.used_at = datetime.now(timezone.utc)
        self._session.flush()
