from api.domain.entities import Identity
from api.domain.ports import IdentityRepositoryPort
from api.infrastructure.auth.passwords import verify_password


class PasswordIdentityVerifier:
    """Today's IdentityVerifierPort implementation: local username+password. A later SSO/social-
    login swap means writing one new class implementing the same port — nothing else in the
    application layer knows or cares which one is wired in."""

    def __init__(self, repository: IdentityRepositoryPort):
        self._repository = repository

    def verify(self, username: str, password: str) -> Identity | None:
        identity = self._repository.get_by_username(username)
        if identity is None or not verify_password(password, identity.password_hash):
            return None
        return identity
