import pytest

from api.application.org_membership_service import OrgMembershipService
from api.application.permission_service import PermissionService
from api.application.profile_service import ProfileService
from api.constants import OBJECT_PERMISSIONS
from api.domain.errors import ConflictError, ForbiddenError, ValidationError
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository


def _org_membership_service(db_session) -> OrgMembershipService:
    return OrgMembershipService(
        OrganizationRepository(db_session),
        OrgMemberRepository(db_session),
        IdentityRepository(db_session),
        ProfileRepository(db_session),
    )


def _identity(db_session, email="owner@acme.com"):
    return IdentityRepository(db_session).create(email, "hashed", name=email)


def test_create_org_with_owner_seeds_working_admin_profile(db_session):
    owner = _identity(db_session)
    db_session.commit()

    organization = _org_membership_service(db_session).create_org_with_owner("Acme Corp", owner.id)
    db_session.commit()

    profiles = ProfileRepository(db_session)
    admin_profile = profiles.get_admin_profile(organization.id)
    assert admin_profile is not None
    assert admin_profile.is_admin is True
    assert set(profiles.list_permissions(admin_profile.id)) == set(OBJECT_PERMISSIONS)

    membership = OrgMemberRepository(db_session).get(organization.id, owner.id)
    assert membership.profile_id == admin_profile.id

    permission_service = PermissionService(OrgMemberRepository(db_session), profiles)
    assert permission_service.resolve_permissions(owner.id, organization.id) == frozenset(OBJECT_PERMISSIONS)


def test_custom_profile_actually_restricts_a_member(db_session):
    owner = _identity(db_session, "owner@acme.com")
    invitee = _identity(db_session, "viewer@acme.com")
    db_session.commit()

    org_service = _org_membership_service(db_session)
    organization = org_service.create_org_with_owner("Acme Corp", owner.id)
    db_session.commit()

    profile_service = ProfileService(ProfileRepository(db_session))
    read_only_profile, _ = profile_service.create(
        organization.id, "Read-only Analyst", "Can look but not touch.", ["documents:read"], owner.id
    )
    db_session.commit()

    org_service.invite_member(organization.id, invitee.email, read_only_profile.id, owner.id)
    db_session.commit()

    permission_service = PermissionService(OrgMemberRepository(db_session), ProfileRepository(db_session))
    granted = permission_service.resolve_permissions(invitee.id, organization.id)
    assert granted == frozenset({"documents:read"})
    assert "documents:write" not in granted


def test_admin_profile_permissions_cannot_be_narrowed(db_session):
    owner = _identity(db_session)
    db_session.commit()
    organization = _org_membership_service(db_session).create_org_with_owner("Acme Corp", owner.id)
    db_session.commit()

    profiles = ProfileRepository(db_session)
    admin_profile = profiles.get_admin_profile(organization.id)
    service = ProfileService(profiles)

    updated, permissions = service.update(organization.id, admin_profile.id, "Admin", "renamed description", [])
    db_session.commit()

    assert updated.description == "renamed description"
    assert set(permissions) == set(OBJECT_PERMISSIONS)


def test_admin_profile_cannot_be_deleted(db_session):
    owner = _identity(db_session)
    db_session.commit()
    organization = _org_membership_service(db_session).create_org_with_owner("Acme Corp", owner.id)
    db_session.commit()

    profiles = ProfileRepository(db_session)
    admin_profile = profiles.get_admin_profile(organization.id)

    with pytest.raises(ForbiddenError):
        ProfileService(profiles).delete(organization.id, admin_profile.id)


def test_profile_in_use_cannot_be_deleted(db_session):
    owner = _identity(db_session, "owner@acme.com")
    invitee = _identity(db_session, "viewer@acme.com")
    db_session.commit()

    org_service = _org_membership_service(db_session)
    organization = org_service.create_org_with_owner("Acme Corp", owner.id)
    db_session.commit()

    profile_service = ProfileService(ProfileRepository(db_session))
    viewer_profile, _ = profile_service.create(organization.id, "Viewer", None, ["documents:read"], owner.id)
    db_session.commit()

    org_service.invite_member(organization.id, invitee.email, viewer_profile.id, owner.id)
    db_session.commit()

    with pytest.raises(ConflictError):
        profile_service.delete(organization.id, viewer_profile.id)


def test_create_profile_rejects_unknown_permission(db_session):
    owner = _identity(db_session)
    db_session.commit()
    organization = _org_membership_service(db_session).create_org_with_owner("Acme Corp", owner.id)
    db_session.commit()

    with pytest.raises(ValidationError):
        ProfileService(ProfileRepository(db_session)).create(
            organization.id, "Bogus", None, ["not:a:real:permission"], owner.id
        )
