from uuid import UUID

from api.domain.entities import Identity
from api.domain.errors import AuthenticationError
from api.domain.ports import IdentityRepositoryPort, IdentityVerifierPort, OrgMemberRepositoryPort
from api.infrastructure.auth.passwords import hash_password


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

    def login(self, email: str, password: str) -> Identity:
        identity = self._verifier.verify(email, password)
        if identity is None:
            raise AuthenticationError("Invalid email or password.")
        return identity

    def list_orgs_for_identity(self, identity_id: UUID) -> list[tuple[UUID, str]]:
        """Returns (org_id, role) pairs — the org switcher's source of truth."""
        return [(member.org_id, member.role) for member in self._org_members.list_for_identity(identity_id)]

    def change_password(self, identity_id: UUID, new_password: str) -> None:
        self._repository.update_password(identity_id, hash_password(new_password))
