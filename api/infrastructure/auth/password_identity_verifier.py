from api.domain.entities import Identity
from api.domain.ports import IdentityRepositoryPort
from api.infrastructure.auth.passwords import hash_password, verify_password

# A fixed, never-matched hash compared against on every login for a username that doesn't exist,
# so verify_password's deliberately slow comparison always runs regardless of whether the identity
# exists — an early return on `identity is None` would otherwise skip it entirely, a timing
# side-channel an attacker could use to enumerate valid usernames (found in a security review).
_DUMMY_PASSWORD_HASH = hash_password("never-a-real-password-only-used-to-equalize-login-timing")


class PasswordIdentityVerifier:
    """Today's IdentityVerifierPort implementation: local username+password. A later SSO/social-
    login swap means writing one new class implementing the same port — nothing else in the
    application layer knows or cares which one is wired in."""

    def __init__(self, repository: IdentityRepositoryPort):
        self._repository = repository

    def verify(self, username: str, password: str) -> Identity | None:
        identity = self._repository.get_by_username(username)
        hashed = identity.password_hash if identity is not None else _DUMMY_PASSWORD_HASH
        if not verify_password(password, hashed):
            return None
        return identity
