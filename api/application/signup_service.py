from api.application.org_membership_service import OrgMembershipService
from api.application.org_name_validation import validate_org_slug
from api.application.username_validation import validate_email_format, validate_username_format
from api.domain.entities import Identity, Organization
from api.domain.ports import IdentityRepositoryPort
from api.infrastructure.auth.passwords import hash_password


class SignupService:
    """Self-serve signup: creates a real identity plus its own personal org (owner/admin role),
    mirroring platform.claude/platform.openai's first-login personal workspace. Unlike that
    platform.claude/platform.openai comparison, this identity can never join a second org later —
    see domain/entities.py's Identity docstring."""

    def __init__(self, identities: IdentityRepositoryPort, org_membership: OrgMembershipService):
        self._identities = identities
        self._org_membership = org_membership

    def signup(self, username: str, password: str, name: str, org_name: str, email: str) -> tuple[Identity, Organization]:
        validate_username_format(username)
        validate_email_format(email)
        validate_org_slug(org_name)
        identity = self._identities.create(
            username, hash_password(password), name=name, email=email, must_change_password=False
        )
        organization = self._org_membership.create_org_with_owner(org_name, identity.id)
        return identity, organization
