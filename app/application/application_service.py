from uuid import UUID

from app.application.scope_validation import validate_scopes_supported
from app.domain import error_codes
from app.domain.entities import Application
from app.domain.errors import NotFoundError, ValidationError
from app.domain.ports import ApplicationRepositoryPort, RefreshTokenRepositoryPort
from app.infrastructure.auth.secrets import generate_secret, hash_secret


class ApplicationService:
    def __init__(self, repository: ApplicationRepositoryPort, refresh_tokens: RefreshTokenRepositoryPort):
        self._repository = repository
        self._refresh_tokens = refresh_tokens

    def register(self, name: str, allowed_scopes: list[str]) -> tuple[str, Application]:
        validate_scopes_supported(allowed_scopes)
        if self._repository.get_by_name(name) is not None:
            raise ValidationError(
                error_codes.APPLICATION_NAME_TAKEN,
                f"An application named '{name}' already exists.",
                field="name",
            )
        raw_secret = generate_secret()
        application = self._repository.create(name, hash_secret(raw_secret), allowed_scopes)
        return raw_secret, application

    def regenerate_secret(self, application_id: UUID) -> str:
        application = self._repository.get(application_id)
        if application is None:
            raise NotFoundError(error_codes.APPLICATION_NOT_FOUND, "Application not found.")
        raw_secret = generate_secret()
        self._repository.update_secret(application_id, hash_secret(raw_secret))
        return raw_secret

    def list_applications(self) -> list[Application]:
        return self._repository.list()

    def revoke_application_token(self, application_id: UUID) -> None:
        application = self._repository.get(application_id)
        if application is None:
            raise NotFoundError(error_codes.APPLICATION_NOT_FOUND, "Application not found.")
        current = self._refresh_tokens.find_current_for_application(application_id)
        if current is not None:
            self._refresh_tokens.revoke(current.id)

    def delete_application(self, application_id: UUID) -> None:
        application = self._repository.get(application_id)
        if application is None:
            raise NotFoundError(error_codes.APPLICATION_NOT_FOUND, "Application not found.")
        self._repository.delete(application_id)
