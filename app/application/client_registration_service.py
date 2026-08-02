from app.constants import DCR_DEFAULT_SCOPES
from app.domain import error_codes
from app.domain.entities import Application
from app.domain.errors import ValidationError
from app.domain.ports import ApplicationRepositoryPort
from app.infrastructure.auth.secrets import generate_secret, hash_secret


class ClientRegistrationService:
    """Backs POST /oauth/register — RFC 7591 Dynamic Client Registration, scoped down to what this
    deployment needs: a client self-registers with a redirect_uri and gets a client_id/secret pair
    back, capped to DCR_DEFAULT_SCOPES rather than letting the caller pick its own scope. Reachable
    only on localhost (same trust boundary the dashboard's own registration already relies on), so
    this deliberately doesn't require prior authentication the way dashboard registration does."""

    def __init__(self, repository: ApplicationRepositoryPort):
        self._repository = repository

    def register_client(self, client_name: str, redirect_uris: list[str]) -> tuple[str, Application]:
        if not redirect_uris:
            raise ValidationError(
                error_codes.INVALID_REQUEST, "redirect_uris is required.", field="redirect_uris"
            )
        raw_secret = generate_secret()
        application = self._repository.create(
            self._unique_name(client_name), hash_secret(raw_secret), DCR_DEFAULT_SCOPES, redirect_uris
        )
        return raw_secret, application

    def _unique_name(self, requested: str) -> str:
        base = requested.strip() if requested and requested.strip() else "mcp-client"
        name = base
        suffix = 1
        while self._repository.get_by_name(name) is not None:
            suffix += 1
            name = f"{base}-{suffix}"
        return name
