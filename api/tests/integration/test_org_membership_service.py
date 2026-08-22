import pytest

from api.application.org_membership_service import OrgMembershipService
from api.domain.errors import ConflictError, ForbiddenError, ValidationError
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository


def _service(db_session) -> OrgMembershipService:
    return OrgMembershipService(
        OrganizationRepository(db_session),
        OrgMemberRepository(db_session),
        IdentityRepository(db_session),
        ProfileRepository(db_session),
    )


def _identity(db_session, username="owner@acme.com"):
    return IdentityRepository(db_session).create(username, "hashed", name=username)


def _org(db_session, service, slug="acme-labs"):
    owner = _identity(db_session, username=f"owner-{slug}@acme.com")
    db_session.commit()
    organization = service.create_org_with_owner(slug, owner.id)
    db_session.commit()
    return organization


def test_invite_member_creates_a_new_identity_for_the_email(db_session):
    service = _service(db_session)
    organization = _org(db_session, service)
    admin_profile = ProfileRepository(db_session).get_admin_profile(organization.id)

    member = service.invite_member(organization.id, "new@acme.com", admin_profile.id, invited_by=None)
    db_session.commit()

    identity = IdentityRepository(db_session).get_by_id(member.identity_id)
    assert identity.username == "new@acme.com"
    assert identity.email == "new@acme.com"


def test_invite_member_rejects_malformed_email(db_session):
    service = _service(db_session)
    organization = _org(db_session, service)
    admin_profile = ProfileRepository(db_session).get_admin_profile(organization.id)

    with pytest.raises(ValidationError):
        service.invite_member(organization.id, "not-an-email", admin_profile.id, invited_by=None)


def test_an_identity_cannot_belong_to_a_second_org(db_session):
    """org_members.identity_id is unique (migration 0013) — an identity belongs to exactly one org
    for its whole life. Simulates this via two invites of the same address into different orgs,
    which under the current invite_member (always creates a new identity, see its docstring) can't
    actually collide — so this exercises the constraint directly via org_members.create instead."""
    service = _service(db_session)
    org_a = _org(db_session, service, slug="org-a")
    org_b = _org(db_session, service, slug="org-b")
    profiles = ProfileRepository(db_session)
    profile_a = profiles.get_admin_profile(org_a.id)
    profile_b = profiles.get_admin_profile(org_b.id)

    identity = _identity(db_session, username="shared@acme.com")
    db_session.commit()

    org_members = OrgMemberRepository(db_session)
    org_members.create(org_a.id, identity.id, profile_a.id)
    db_session.commit()

    with pytest.raises(ConflictError):
        org_members.create(org_b.id, identity.id, profile_b.id)


def test_admin_cannot_change_own_profile(db_session):
    service = _service(db_session)
    organization = _org(db_session, service)
    profiles = ProfileRepository(db_session)
    contributor_profile = profiles.get_by_name(organization.id, "Contributor")
    admin_member = OrgMemberRepository(db_session).list_for_org(organization.id)[0]

    with pytest.raises(ForbiddenError):
        service.update_member_profile(
            organization.id, admin_member.identity_id, contributor_profile.id, acting_identity_id=admin_member.identity_id
        )


def test_admin_can_change_another_members_profile(db_session):
    service = _service(db_session)
    organization = _org(db_session, service)
    profiles = ProfileRepository(db_session)
    admin_profile = profiles.get_admin_profile(organization.id)
    contributor_profile = profiles.get_by_name(organization.id, "Contributor")
    admin_member = OrgMemberRepository(db_session).list_for_org(organization.id)[0]

    other = service.invite_member(organization.id, "other@acme.com", contributor_profile.id, invited_by=None)
    db_session.commit()

    updated = service.update_member_profile(
        organization.id, other.identity_id, admin_profile.id, acting_identity_id=admin_member.identity_id
    )
    db_session.commit()

    assert updated.profile_id == admin_profile.id
