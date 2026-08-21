import secrets
from uuid import UUID

from api.application.profile_service import ProfileService
from api.application.slugify import slugify
from api.domain import error_codes
from api.domain.entities import Identity, OrgMember, Organization
from api.domain.errors import ConflictError, NotFoundError
from api.domain.ports import (
    IdentityRepositoryPort,
    OrgMemberRepositoryPort,
    OrganizationRepositoryPort,
    ProfileRepositoryPort,
)
from api.infrastructure.auth.passwords import hash_password

# Retry budget for personal-org slug collisions (see create_org_with_owner) — collisions are rare
# (same email local-part, different domain) and a handful of random suffixes is plenty; this isn't
# a value that changes without a redeploy, so it stays a plain local constant, not api.constants.
_SLUG_COLLISION_RETRIES = 5


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
        """Self-serve org creation — used both for a new signup's personal org and for "create
        another org" later. Retries the slug with a random suffix on collision rather than failing
        the whole signup over a cosmetic slug clash."""
        base_slug = slugify(name)
        for attempt in range(_SLUG_COLLISION_RETRIES):
            slug = base_slug if attempt == 0 else f"{base_slug}-{secrets.token_hex(2)}"
            try:
                organization = self._organizations.create(
                    name, slug, created_by=owner_identity_id, last_modified_by=owner_identity_id
                )
                break
            except ConflictError:
                continue
        else:
            raise ConflictError(error_codes.ORGANIZATION_SLUG_TAKEN, f"Could not allocate a slug for '{name}'.")
        profile_service = ProfileService(self._profiles)
        admin_profile = profile_service.create_admin_profile(organization.id, owner_identity_id)
        # Contributor/Viewer are seeded alongside Admin for every org — see ProfileService's
        # docstrings and api/constants.py's DEFAULT_CONTRIBUTOR_PERMISSIONS/DEFAULT_VIEWER_PERMISSIONS.
        profile_service.create_contributor_profile(organization.id, owner_identity_id)
        profile_service.create_viewer_profile(organization.id, owner_identity_id)
        self._org_members.create(organization.id, owner_identity_id, admin_profile.id)
        return organization

    def invite_member(self, org_id: UUID, email: str, profile_id: UUID, invited_by: UUID) -> OrgMember:
        """If no identity exists yet for this email, creates one with an unusable random password
        (must_change_password=True) so the invitee sets their own on first login — same pattern
        this app already uses for the bootstrap admin identity. profile_id must be one of this
        org's existing profiles (Admin, or a custom one already created) — there's no guaranteed
        non-admin default to fall back to since profiles are custom per org."""
        identity = self._identities.get_by_email(email)
        if identity is None:
            identity = self._identities.create(email, hash_password(secrets.token_urlsafe(32)), name=email)
        return self._org_members.create(org_id, identity.id, profile_id, invited_by=invited_by)

    def update_organization(self, org_id: UUID, name: str, description: str | None) -> Organization:
        if self._organizations.get(org_id) is None:
            raise NotFoundError(error_codes.ORGANIZATION_NOT_FOUND, "Organization not found.")
        return self._organizations.update(org_id, name=name, description=description)

    def switch_active_org(self, identity_id: UUID, org_id: UUID) -> None:
        """Validates membership only — the active org's permissions are resolved fresh on every
        request (PermissionService), never cached in the session, so there's nothing to return
        here anymore."""
        member = self._org_members.get(org_id, identity_id)
        if member is None:
            raise NotFoundError(error_codes.NOT_AN_ORG_MEMBER, "You are not a member of this organization.")

    def update_member_profile(self, org_id: UUID, identity_id: UUID, profile_id: UUID) -> OrgMember:
        return self._org_members.update_profile(org_id, identity_id, profile_id)

    def remove_member(self, org_id: UUID, identity_id: UUID) -> None:
        self._org_members.delete(org_id, identity_id)

    def list_members(self, org_id: UUID) -> list[tuple[OrgMember, Identity]]:
        members = self._org_members.list_for_org(org_id)
        return [(member, self._identities.get_by_id(member.identity_id)) for member in members]
