import secrets
from uuid import UUID

from api.application.org_name_validation import validate_org_slug
from api.application.profile_service import ProfileService
from api.application.username_validation import validate_username_format
from api.domain import error_codes
from api.domain.entities import Identity, OrgMember, Organization
from api.domain.errors import AuthenticationError, ForbiddenError
from api.domain.ports import (
    IdentityRepositoryPort,
    OrgMemberRepositoryPort,
    OrganizationRepositoryPort,
    ProfileRepositoryPort,
)
from api.infrastructure.auth.passwords import hash_password, verify_password


class OrgMembershipService:
    def __init__(
        self,
        organizations: OrganizationRepositoryPort,
        org_members: OrgMemberRepositoryPort,
        identities: IdentityRepositoryPort,
        profiles: ProfileRepositoryPort,
    ):
        self._organizations = organizations
        self._org_members = org_members
        self._identities = identities
        self._profiles = profiles

    def create_org_with_owner(self, name: str, owner_identity_id: UUID) -> Organization:
        """Self-serve org creation, used only at signup — an identity/username belongs to exactly
        one org for its whole life (see domain/entities.py's Identity docstring), so this only ever
        runs once per identity. `name` is already a user-chosen, slug-shaped identifier (see
        org_name_validation.validate_org_slug) and is stored verbatim as both the org's name and
        its slug; a collision surfaces as a plain ConflictError, not a silent rename."""
        organization = self._organizations.create(
            name, name, created_by=owner_identity_id, last_modified_by=owner_identity_id
        )
        profile_service = ProfileService(self._profiles)
        admin_profile = profile_service.create_admin_profile(organization.id, owner_identity_id)
        # Contributor/Viewer are seeded alongside Admin for every org — see ProfileService's
        # docstrings and api/constants.py's DEFAULT_CONTRIBUTOR_PERMISSIONS/DEFAULT_VIEWER_PERMISSIONS.
        profile_service.create_contributor_profile(organization.id, owner_identity_id)
        profile_service.create_viewer_profile(organization.id, owner_identity_id)
        self._org_members.create(organization.id, owner_identity_id, admin_profile.id)
        return organization

    def invite_member(self, org_id: UUID, email: str, profile_id: UUID, invited_by: UUID) -> OrgMember:
        """Creates a brand-new identity for the invitee, with an unusable random password
        (must_change_password=True) so they set their own on first login — same pattern this app
        already uses for the bootstrap admin identity. Always creates a new identity rather than
        reusing an existing one at this email: since org_members.identity_id is unique, an existing
        identity already belongs to a different org and can't be added to a second one, and since
        email is no longer unique there may be zero, one, or several existing identities at this
        address anyway. Stopgap: `username` defaults to `email` here, pending a proper invite-flow
        redesign (letting the inviter choose a username directly) — a collision with an existing
        username surfaces as a plain ConflictError for now. profile_id must be one of this org's
        existing profiles (Admin, or a custom one already created) — there's no guaranteed
        non-admin default to fall back to since profiles are custom per org."""
        validate_username_format(email)
        identity = self._identities.create(
            email, hash_password(secrets.token_urlsafe(32)), name=email, email=email
        )
        return self._org_members.create(org_id, identity.id, profile_id, invited_by=invited_by)

    def update_member_profile(
        self, org_id: UUID, identity_id: UUID, profile_id: UUID, *, acting_identity_id: UUID
    ) -> OrgMember:
        """An admin can change any *other* member's profile (promote/demote between admin and
        standard profiles freely) but never their own — prevents both accidental self-lockout (the
        last admin demoting themselves with no one left to undo it) and self-escalation by a
        standard member who somehow reaches this endpoint. Enforced here, not just left to the
        frontend disabling the control, since this is a real authorization rule, not a UX nicety."""
        if identity_id == acting_identity_id:
            raise ForbiddenError("You can't change your own profile — ask another admin to change it.")
        return self._org_members.update_profile(org_id, identity_id, profile_id)

    def change_organization_name(
        self, org_id: UUID, acting_identity_id: UUID, current_password: str, new_name: str
    ) -> Organization:
        """Gated at the route by org:write (only the Admin profile has it by default — see
        OBJECT_PERMISSIONS/ProfileService.create_admin_profile). Re-verifies the acting admin's
        own current password first, same rationale as AuthService.change_username: the org name
        doubles as every member's URL slug (validate_org_slug / migration 0014's name==slug
        invariant), so a hijacked session shouldn't be able to silently rewrite the whole org's
        address just by holding the cookie."""
        identity = self._identities.get_by_id(acting_identity_id)
        if identity is None or not verify_password(current_password, identity.password_hash):
            raise AuthenticationError("Incorrect password.", code=error_codes.INCORRECT_PASSWORD)
        validate_org_slug(new_name)
        return self._organizations.update_name(org_id, new_name)

    def remove_member(self, org_id: UUID, identity_id: UUID) -> None:
        self._org_members.delete(org_id, identity_id)

    def list_members(self, org_id: UUID) -> list[tuple[OrgMember, Identity]]:
        members = self._org_members.list_for_org(org_id)
        return [(member, self._identities.get_by_id(member.identity_id)) for member in members]
