from uuid import UUID

from app.domain.entities import Application as ApplicationEntity
from app.infrastructure.orm import Application as ApplicationModel


def _to_entity(model: ApplicationModel) -> ApplicationEntity:
    return ApplicationEntity(
        id=model.id,
        name=model.name,
        allowed_scopes=model.allowed_scopes.split(),
        created_at=model.created_at,
        redirect_uris=model.redirect_uris.split() if model.redirect_uris else [],
    )


class ApplicationRepository:
    def __init__(self, session):
        self._session = session

    def create(
        self,
        name: str,
        client_secret_hash: str,
        allowed_scopes: list[str],
        redirect_uris: list[str] | None = None,
        id: UUID | None = None,
    ) -> ApplicationEntity:
        model = ApplicationModel(
            name=name,
            client_secret_hash=client_secret_hash,
            allowed_scopes=" ".join(allowed_scopes),
            redirect_uris=" ".join(redirect_uris) if redirect_uris else None,
        )
        if id is not None:
            model.id = id
        self._session.add(model)
        self._session.flush()
        return _to_entity(model)

    # Placed before list() below, deliberately — a bare `list[str]` annotation on any method
    # defined *after* list() would resolve `list` to that method itself (shadowing the builtin in
    # this class's namespace), not the builtin generic, and blow up at class-definition time.
    def update_scopes(self, application_id: UUID, allowed_scopes: list[str]) -> None:
        model = self._session.query(ApplicationModel).filter(ApplicationModel.id == application_id).one()
        model.allowed_scopes = " ".join(allowed_scopes)
        self._session.flush()

    def list(self) -> list[ApplicationEntity]:
        models = self._session.query(ApplicationModel).order_by(ApplicationModel.created_at).all()
        return [_to_entity(model) for model in models]

    def get(self, application_id: UUID) -> ApplicationEntity | None:
        model = self._session.query(ApplicationModel).filter(ApplicationModel.id == application_id).first()
        return _to_entity(model) if model is not None else None

    def get_by_name(self, name: str) -> ApplicationEntity | None:
        model = self._session.query(ApplicationModel).filter(ApplicationModel.name == name).first()
        return _to_entity(model) if model is not None else None

    def find_by_credentials(self, application_id: UUID, client_secret_hash: str) -> ApplicationEntity | None:
        model = (
            self._session.query(ApplicationModel)
            .filter(ApplicationModel.id == application_id)
            .filter(ApplicationModel.client_secret_hash == client_secret_hash)
            .first()
        )
        return _to_entity(model) if model is not None else None

    def update_secret(self, application_id: UUID, client_secret_hash: str) -> None:
        model = self._session.query(ApplicationModel).filter(ApplicationModel.id == application_id).one()
        model.client_secret_hash = client_secret_hash
        self._session.flush()

    def delete(self, application_id: UUID) -> None:
        # refresh_tokens.application_id has ondelete="CASCADE" (migration 0004), so this also
        # removes any refresh tokens belonging to the application — no separate cleanup needed.
        model = self._session.query(ApplicationModel).filter(ApplicationModel.id == application_id).first()
        if model is not None:
            self._session.delete(model)
            self._session.flush()
