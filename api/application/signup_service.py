from api.application.org_membership_service import OrgMembershipService
from api.application.org_name_validation import validate_org_slug
from api.domain.entities import Identity, Organization
from api.domain.ports import IdentityRepositoryPort
from api.infrastructure.auth.passwords import hash_password


class SignupService:
    """Self-serve signup: creates a real identity plus its own personal org (owner/admin role),
    mirroring platform.claude/platform.openai's first-login personal workspace."""

    def __init__(self, identities: IdentityRepositoryPort, org_membership: OrgMembershipService):
        self._identities = identities
        self._org_membership = org_membership

    def signup(self, email: str, password: str, name: str, org_name: str) -> tuple[Identity, Organization]:
        validate_org_slug(org_name)
        identity = self._identities.create(email, hash_password(password), name=name, must_change_password=False)
        organization = self._org_membership.create_org_with_owner(org_name, identity.id, exact_slug=True)
        return identity, organization
