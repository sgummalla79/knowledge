from datetime import datetime, timezone
from uuid import UUID

from api.domain.entities import PersonalAccessToken as PersonalAccessTokenEntity
from api.infrastructure.orm.personal_access_token import PersonalAccessToken as PersonalAccessTokenModel


def _to_entity(model: PersonalAccessTokenModel) -> PersonalAccessTokenEntity:
    return PersonalAccessTokenEntity(
        id=model.id,
        identity_id=model.identity_id,
        org_id=model.org_id,
        name=model.name,
        token_hash=model.token_hash,
        token_prefix=model.token_prefix,
        mcp_access=model.mcp_access,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )


class PersonalAccessTokenRepository:
    def __init__(self, session):
        self._session = session

    def create(
        self, identity_id: UUID, org_id: UUID, name: str, token_hash: str, token_prefix: str, mcp_access: bool
    ) -> PersonalAccessTokenEntity:
        model = PersonalAccessTokenModel(
            identity_id=identity_id,
            org_id=org_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            mcp_access=mcp_access,
        )
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get_by_token_hash(self, token_hash: str) -> PersonalAccessTokenEntity | None:
        model = (
            self._session.query(PersonalAccessTokenModel)
            .filter(PersonalAccessTokenModel.token_hash == token_hash)
            .first()
        )
        return _to_entity(model) if model is not None else None

    def get_by_id(self, token_id: UUID) -> PersonalAccessTokenEntity | None:
        model = self._session.get(PersonalAccessTokenModel, token_id)
        return _to_entity(model) if model is not None else None

    def list_for_identity_in_org(self, identity_id: UUID, org_id: UUID) -> list[PersonalAccessTokenEntity]:
        models = (
            self._session.query(PersonalAccessTokenModel)
            .filter(PersonalAccessTokenModel.identity_id == identity_id, PersonalAccessTokenModel.org_id == org_id)
            .order_by(PersonalAccessTokenModel.created_at.desc())
            .all()
        )
        return [_to_entity(model) for model in models]

    def touch_last_used(self, token_id: UUID) -> None:
        model = self._session.get(PersonalAccessTokenModel, token_id)
        if model is not None:
            model.last_used_at = datetime.now(timezone.utc)
            self._session.flush()

    def delete(self, token_id: UUID) -> None:
        model = self._session.get(PersonalAccessTokenModel, token_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()
