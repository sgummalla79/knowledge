import pytest

from api.application.org_membership_service import OrgMembershipService
from api.application.signup_service import SignupService
from api.domain.errors import ConflictError, ValidationError
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository


def _signup_service(db_session) -> SignupService:
    identities = IdentityRepository(db_session)
    org_membership = OrgMembershipService(
        OrganizationRepository(db_session), OrgMemberRepository(db_session), identities, ProfileRepository(db_session)
    )
    return SignupService(identities, org_membership)


def test_signup_creates_org_with_name_and_slug_equal_to_org_name(db_session):
    _identity, organization = _signup_service(db_session).signup(
        "ada@acme.com", "a-strong-password", "Ada", "ada-labs", "ada-contact@acme.com"
    )
    db_session.commit()

    assert organization.name == "ada-labs"
    assert organization.slug == "ada-labs"


def test_signup_rejects_malformed_org_name_without_creating_identity(db_session):
    with pytest.raises(ValidationError):
        _signup_service(db_session).signup(
            "ada@acme.com", "a-strong-password", "Ada", "Not Slug!", "ada-contact@acme.com"
        )
    db_session.commit()

    assert IdentityRepository(db_session).get_by_username("ada@acme.com") is None


def test_signup_rejects_malformed_username(db_session):
    with pytest.raises(ValidationError):
        _signup_service(db_session).signup(
            "not-an-email", "a-strong-password", "Ada", "ada-labs", "ada-contact@acme.com"
        )
    db_session.commit()

    assert IdentityRepository(db_session).get_by_username("not-an-email") is None


def test_signup_rejects_malformed_email(db_session):
    with pytest.raises(ValidationError):
        _signup_service(db_session).signup(
            "ada@acme.com", "a-strong-password", "Ada", "ada-labs", "not-an-email"
        )
    db_session.commit()

    assert IdentityRepository(db_session).get_by_username("ada@acme.com") is None


def test_signup_stores_email_separately_from_username(db_session):
    identity, _organization = _signup_service(db_session).signup(
        "ada-login@acme.com", "a-strong-password", "Ada", "ada-labs", "ada-contact@acme.com"
    )
    db_session.commit()

    assert identity.username == "ada-login@acme.com"
    assert identity.email == "ada-contact@acme.com"


def test_signup_allows_duplicate_email_across_different_usernames(db_session):
    service = _signup_service(db_session)
    service.signup("ada@acme.com", "a-strong-password", "Ada", "ada-labs", "shared@acme.com")
    db_session.commit()

    identity, _organization = service.signup(
        "bea@acme.com", "a-strong-password", "Bea", "bea-labs", "shared@acme.com"
    )
    db_session.commit()

    assert identity.email == "shared@acme.com"


def test_signup_rejects_taken_org_name_instead_of_renaming(db_session):
    service = _signup_service(db_session)
    service.signup("ada@acme.com", "a-strong-password", "Ada", "acme-labs", "ada-contact@acme.com")
    db_session.commit()

    with pytest.raises(ConflictError):
        service.signup("bea@acme.com", "a-strong-password", "Bea", "acme-labs", "bea-contact@acme.com")
    db_session.commit()
