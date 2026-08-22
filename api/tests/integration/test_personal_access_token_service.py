from uuid import uuid4

import pytest

from api.application.app_auth_service import AppAuthService
from api.application.permission_service import PermissionService
from api.application.personal_access_token_service import PersonalAccessTokenService
from api.application.profile_service import ProfileService
from api.domain.errors import NotFoundError
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository


@pytest.fixture()
def org_id(db_session):
    return bootstrap_default_organization(db_session).id


def _service(db_session) -> PersonalAccessTokenService:
    return PersonalAccessTokenService(PersonalAccessTokenRepository(db_session))


def _auth_service(db_session) -> AppAuthService:
    return AppAuthService(
        ApplicationRepository(db_session),
        PersonalAccessTokenRepository(db_session),
        PermissionService(OrgMemberRepository(db_session), ProfileRepository(db_session)),
    )


def _member_with_profile(db_session, org_id, permissions, email):
    # Attaches org membership directly rather than via OrgMembershipService.invite_member, which
    # always creates a brand-new identity now (an identity belongs to exactly one org for its whole
    # life — org_members.identity_id is unique) — this helper needs to add *this* already-created
    # identity to *this* org, not mint a second one at the same email.
    identity = IdentityRepository(db_session).create(email, "hashed", name=email)
    db_session.commit()
    profile, _ = ProfileService(ProfileRepository(db_session)).create(org_id, f"profile-{email}", None, permissions, None)
    db_session.commit()
    OrgMemberRepository(db_session).create(org_id, identity.id, profile.id)
    db_session.commit()
    return identity


def test_created_token_authenticates_with_owners_current_profile(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "owner@acme.com")
    service = _service(db_session)

    token, raw_token = service.create(org_id, member.id, "My laptop")
    db_session.commit()

    assert len(raw_token) > 20
    assert token.mcp_access is False

    caller = _auth_service(db_session).authenticate_bearer_token(raw_token)
    assert caller.org_id == org_id
    assert caller.identity_id == member.id
    assert caller.application_id is None
    assert caller.auth_method == "personal_access_token"
    assert caller.api_access is True
    assert caller.scopes == frozenset({"documents:read"})


def test_wrong_token_is_rejected(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "wrong@acme.com")
    service = _service(db_session)
    service.create(org_id, member.id, "My laptop")
    db_session.commit()

    assert _auth_service(db_session).authenticate_bearer_token("not-the-real-token") is None


def test_token_reflects_current_permissions_not_baked_in(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "changing@acme.com")
    service = _service(db_session)
    _, raw_token = service.create(org_id, member.id, "My laptop")
    db_session.commit()

    membership = OrgMemberRepository(db_session).get(org_id, member.id)
    ProfileService(ProfileRepository(db_session)).update(
        org_id, membership.profile_id, "profile-changing", None, ["documents:write"]
    )
    db_session.commit()

    caller = _auth_service(db_session).authenticate_bearer_token(raw_token)
    assert caller.scopes == frozenset({"documents:write"})


def test_mcp_access_defaults_to_false_and_persists_when_set(db_session, org_id):
    member = _member_with_profile(db_session, org_id, [], "mcp@acme.com")
    service = _service(db_session)

    default_token, _ = service.create(org_id, member.id, "default")
    mcp_token, raw_token = service.create(org_id, member.id, "with mcp", mcp_access=True)
    db_session.commit()

    assert default_token.mcp_access is False
    assert mcp_token.mcp_access is True

    caller = _auth_service(db_session).authenticate_bearer_token(raw_token)
    assert caller.mcp_access is True


def test_list_for_identity_scoped_to_org_and_owner(db_session, org_id):
    other_org_id = OrganizationRepository(db_session).create("Other Org", "other-org").id
    db_session.commit()
    member = _member_with_profile(db_session, org_id, [], "lister@acme.com")
    other_member = _member_with_profile(db_session, org_id, [], "other@acme.com")
    service = _service(db_session)

    service.create(org_id, member.id, "mine in this org")
    service.create(other_org_id, member.id, "mine in another org")
    service.create(org_id, other_member.id, "not mine")
    db_session.commit()

    tokens = service.list_for_identity(org_id, member.id)

    assert [token.name for token in tokens] == ["mine in this org"]


def test_delete_removes_the_token(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "deleter@acme.com")
    service = _service(db_session)
    token, raw_token = service.create(org_id, member.id, "to delete")
    db_session.commit()

    service.delete(member.id, token.id)
    db_session.commit()

    assert _auth_service(db_session).authenticate_bearer_token(raw_token) is None
    assert service.list_for_identity(org_id, member.id) == []


def test_delete_someone_elses_token_is_not_found(db_session, org_id):
    owner = _member_with_profile(db_session, org_id, [], "real-owner@acme.com")
    other = _member_with_profile(db_session, org_id, [], "not-owner@acme.com")
    service = _service(db_session)
    token, _ = service.create(org_id, owner.id, "owner's key")
    db_session.commit()

    with pytest.raises(NotFoundError):
        service.delete(other.id, token.id)


def test_delete_unknown_token_is_not_found(db_session, org_id):
    member = _member_with_profile(db_session, org_id, [], "solo@acme.com")

    with pytest.raises(NotFoundError):
        _service(db_session).delete(member.id, uuid4())
