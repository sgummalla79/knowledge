import pytest

from api.application.org_membership_service import OrgMembershipService
from api.domain import error_codes
from api.domain.errors import AuthenticationError, ConflictError, ForbiddenError, ValidationError
from api.infrastructure.auth.passwords import hash_password
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


def _identity(db_session, username="owner@acme.com", password_hash="hashed"):
    return IdentityRepository(db_session).create(username, password_hash, name=username)


def _org(db_session, service, slug="acme-labs"):
    owner = _identity(db_session, username=f"owner-{slug}@acme.com")
    db_session.commit()
    organization = service.create_org_with_owner(slug, owner.id)
    db_session.commit()
    return organization


def _org_with_admin_password(db_session, service, slug, password):
    """Like _org, but the owner identity gets a real, verifiable password hash — needed for
    change_organization_name's current_password check, which _org's plain "hashed" placeholder
    can't satisfy."""
    owner = _identity(db_session, username=f"owner-{slug}@acme.com", password_hash=hash_password(password))
    db_session.commit()
    organization = service.create_org_with_owner(slug, owner.id)
    db_session.commit()
    return organization, owner


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


def test_change_organization_name_succeeds_with_correct_password(db_session):
    service = _service(db_session)
    organization, owner = _org_with_admin_password(db_session, service, "acme-rename-ok", "correct-password")

    updated = service.change_organization_name(organization.id, owner.id, "correct-password", "acme-renamed")
    db_session.commit()

    assert updated.name == "acme-renamed"
    assert updated.slug == "acme-renamed"
    assert OrganizationRepository(db_session).get_by_slug("acme-renamed") is not None


def test_change_organization_name_rejects_wrong_password(db_session):
    """Regression test: a wrong re-verification password must carry the distinct
    INCORRECT_PASSWORD code, not the generic UNAUTHORIZED one -- see
    test_auth_service.py::test_change_username_rejects_wrong_password's own note for why."""
    service = _service(db_session)
    organization, owner = _org_with_admin_password(db_session, service, "acme-rename-wrongpw", "correct-password")

    with pytest.raises(AuthenticationError) as exc_info:
        service.change_organization_name(organization.id, owner.id, "wrong-password", "acme-renamed-wrongpw")
    db_session.commit()

    assert exc_info.value.code == error_codes.INCORRECT_PASSWORD
    assert OrganizationRepository(db_session).get(organization.id).slug == "acme-rename-wrongpw"


def test_change_organization_name_rejects_invalid_slug(db_session):
    service = _service(db_session)
    organization, owner = _org_with_admin_password(db_session, service, "acme-rename-invalid", "correct-password")

    with pytest.raises(ValidationError):
        service.change_organization_name(organization.id, owner.id, "correct-password", "Not A Slug")


def test_change_organization_name_rejects_taken_slug(db_session):
    service = _service(db_session)
    _org(db_session, service, slug="acme-taken")
    organization, owner = _org_with_admin_password(db_session, service, "acme-rename-taken", "correct-password")

    with pytest.raises(ConflictError):
        service.change_organization_name(organization.id, owner.id, "correct-password", "acme-taken")
