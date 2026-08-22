from uuid import UUID

from api.application.username_validation import validate_email_format, validate_username_format
from api.domain.entities import Identity
from api.domain.errors import AuthenticationError
from api.domain.ports import IdentityRepositoryPort, IdentityVerifierPort, OrgMemberRepositoryPort
from api.infrastructure.auth.passwords import hash_password, verify_password


class AuthService:
    def __init__(
        self,
        repository: IdentityRepositoryPort,
        verifier: IdentityVerifierPort,
        org_members: OrgMemberRepositoryPort,
    ):
        self._repository = repository
        self._verifier = verifier
        self._org_members = org_members

    def login(self, username: str, password: str) -> Identity:
        identity = self._verifier.verify(username, password)
        if identity is None:
            raise AuthenticationError("Invalid username or password.")
        return identity

    def list_orgs_for_identity(self, identity_id: UUID) -> list[UUID]:
        """Resolves the org to activate on login — always exactly 0 or 1 org, since an identity
        belongs to at most one org for its whole life (org_members.identity_id is unique). Kept
        list-shaped rather than Optional[UUID] since _establish_session's "no membership yet"
        branch already handles an empty result the same way it always has."""
        return [member.org_id for member in self._org_members.list_for_identity(identity_id)]

    def change_password(self, identity_id: UUID, new_password: str) -> None:
        self._repository.update_password(identity_id, hash_password(new_password))

    def update_profile(self, identity_id: UUID, name: str, email: str) -> Identity:
        validate_email_format(email)
        return self._repository.update_profile(identity_id, name=name, email=email)

    def change_username(self, identity_id: UUID, current_password: str, new_username: str) -> Identity:
        """Unlike change_password (used by the forced first-login flow, where the caller doesn't
        necessarily know their current password), this is a deliberate self-service action by an
        already-logged-in user changing their own login credential — current_password confirms
        it's really them before the credential changes, not just whoever holds the session cookie
        right now."""
        identity = self._repository.get_by_id(identity_id)
        if identity is None or not verify_password(current_password, identity.password_hash):
            raise AuthenticationError("Incorrect password.")
        validate_username_format(new_username)
        return self._repository.update_username(identity_id, new_username)
