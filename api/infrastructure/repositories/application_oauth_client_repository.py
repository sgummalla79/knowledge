from datetime import datetime, timezone
from uuid import UUID

from api.domain.entities import ApplicationOAuthClient as ApplicationOAuthClientEntity
from api.infrastructure.orm.application_oauth_client import ApplicationOAuthClient as ApplicationOAuthClientModel


def _to_entity(model: ApplicationOAuthClientModel) -> ApplicationOAuthClientEntity:
    return ApplicationOAuthClientEntity(
        id=model.id,
        application_id=model.application_id,
        client_secret_hash=model.client_secret_hash,
        redirect_uris=list(model.redirect_uris or []),
        created_at=model.created_at,
        last_rotated_at=model.last_rotated_at,
        revoked_at=model.revoked_at,
    )


class ApplicationOAuthClientRepository:
    def __init__(self, session):
        self._session = session

    def create(
        self, application_id: UUID, client_secret_hash: str | None, redirect_uris: list[str] | None = None
    ) -> ApplicationOAuthClientEntity:
        model = ApplicationOAuthClientModel(
            application_id=application_id, client_secret_hash=client_secret_hash, redirect_uris=redirect_uris or []
        )
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    def get_by_application(self, application_id: UUID) -> ApplicationOAuthClientEntity | None:
        model = (
            self._session.query(ApplicationOAuthClientModel)
            .filter(ApplicationOAuthClientModel.application_id == application_id)
            .first()
        )
        return _to_entity(model) if model is not None else None

    def rotate(self, application_id: UUID, client_secret_hash: str) -> ApplicationOAuthClientEntity:
        model = (
            self._session.query(ApplicationOAuthClientModel)
            .filter(ApplicationOAuthClientModel.application_id == application_id)
            .first()
        )
        model.client_secret_hash = client_secret_hash
        model.last_rotated_at = datetime.now(timezone.utc)
        self._session.flush()
        return _to_entity(model)
