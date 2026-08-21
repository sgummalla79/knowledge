from datetime import datetime, timezone
from uuid import UUID

from api.domain.entities import ApplicationApiKey as ApplicationApiKeyEntity
from api.infrastructure.orm.application_api_key import ApplicationApiKey as ApplicationApiKeyModel


def _to_entity(model: ApplicationApiKeyModel) -> ApplicationApiKeyEntity:
    return ApplicationApiKeyEntity(
        id=model.id,
        application_id=model.application_id,
        key_hash=model.key_hash,
        key_prefix=model.key_prefix,
        created_at=model.created_at,
        last_rotated_at=model.last_rotated_at,
        last_used_at=model.last_used_at,
        revoked_at=model.revoked_at,
    )


class ApplicationApiKeyRepository:
    def __init__(self, session):
        self._session = session

    def create(self, application_id: UUID, key_hash: str, key_prefix: str) -> ApplicationApiKeyEntity:
        model = ApplicationApiKeyModel(application_id=application_id, key_hash=key_hash, key_prefix=key_prefix)
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get_by_key_hash(self, key_hash: str) -> ApplicationApiKeyEntity | None:
        model = self._session.query(ApplicationApiKeyModel).filter(ApplicationApiKeyModel.key_hash == key_hash).first()
        return _to_entity(model) if model is not None else None

    def _get_for_application(self, application_id: UUID) -> ApplicationApiKeyModel | None:
        return (
            self._session.query(ApplicationApiKeyModel)
            .filter(ApplicationApiKeyModel.application_id == application_id)
            .first()
        )

    def rotate(self, application_id: UUID, key_hash: str, key_prefix: str) -> ApplicationApiKeyEntity:
        model = self._get_for_application(application_id)
        model.key_hash = key_hash
        model.key_prefix = key_prefix
        model.last_rotated_at = datetime.now(timezone.utc)
        self._session.flush()
        return _to_entity(model)

    def touch_last_used(self, application_id: UUID) -> None:
        model = self._get_for_application(application_id)
        if model is not None:
            model.last_used_at = datetime.now(timezone.utc)
            self._session.flush()
