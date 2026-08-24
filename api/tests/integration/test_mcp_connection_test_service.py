import pytest

from api.application.app_auth_service import AppAuthService
from api.application.mcp_connection_test_service import MCPConnectionTestService
from api.application.mcp_settings_service import MCPSettingsService
from api.application.permission_service import PermissionService
from api.application.personal_access_token_service import PersonalAccessTokenService
from api.application.profile_service import ProfileService
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.mcp_settings_repository import MCPSettingsRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository


@pytest.fixture()
def org_id(db_session):
    return bootstrap_default_organization(db_session).id


def _service(db_session) -> MCPConnectionTestService:
    permissions = PermissionService(OrgMemberRepository(db_session), ProfileRepository(db_session))
    app_auth = AppAuthService(
        ApplicationRepository(db_session), PersonalAccessTokenRepository(db_session), permissions
    )
    return MCPConnectionTestService(app_auth, MCPSettingsRepository(db_session))


def _member_with_token(db_session, org_id, *, mcp_access, email):
    identity = IdentityRepository(db_session).create(email, "hashed", name=email)
    db_session.commit()
    profile, _ = ProfileService(ProfileRepository(db_session)).create(org_id, f"profile-{email}", None, [], None)
    db_session.commit()
    OrgMemberRepository(db_session).create(org_id, identity.id, profile.id)
    db_session.commit()
    _, raw_token = PersonalAccessTokenService(PersonalAccessTokenRepository(db_session)).create(
        org_id, identity.id, "test token", mcp_access=mcp_access
    )
    db_session.commit()
    return raw_token


def test_invalid_token_is_rejected(db_session, org_id):
    result = _service(db_session).test(org_id, "search", "not-a-real-token")

    assert result.ok is False
    assert result.reason == "invalid_token"


def test_unknown_tier_is_rejected(db_session, org_id):
    token = _member_with_token(db_session, org_id, mcp_access=True, email="unknown-tier@acme.com")

    result = _service(db_session).test(org_id, "not-a-real-tier", token)

    assert result.ok is False
    assert result.reason == "unknown_tier"


def test_token_without_mcp_access_is_rejected(db_session, org_id):
    token = _member_with_token(db_session, org_id, mcp_access=False, email="no-mcp@acme.com")
    MCPSettingsService(MCPSettingsRepository(db_session)).update(org_id, True, True, True, None)
    db_session.commit()

    result = _service(db_session).test(org_id, "search", token)

    assert result.ok is False
    assert result.reason == "no_mcp_access"


def test_disabled_tier_is_rejected(db_session, org_id):
    token = _member_with_token(db_session, org_id, mcp_access=True, email="disabled-tier@acme.com")

    result = _service(db_session).test(org_id, "search", token)

    assert result.ok is False
    assert result.reason == "tier_disabled"


def test_token_belonging_to_a_different_org_is_rejected(db_session, org_id):
    other_org_id = OrganizationRepository(db_session).create("Other Org", "other-org").id
    db_session.commit()
    token = _member_with_token(db_session, other_org_id, mcp_access=True, email="wrong-org@acme.com")
    MCPSettingsService(MCPSettingsRepository(db_session)).update(org_id, True, True, True, None)
    db_session.commit()

    result = _service(db_session).test(org_id, "search", token)

    assert result.ok is False
    assert result.reason == "wrong_org"


def test_valid_token_for_an_enabled_tier_succeeds(db_session, org_id):
    token = _member_with_token(db_session, org_id, mcp_access=True, email="ok@acme.com")
    MCPSettingsService(MCPSettingsRepository(db_session)).update(org_id, True, False, False, None)
    db_session.commit()

    result = _service(db_session).test(org_id, "search", token)

    assert result.ok is True
    assert result.reason == "ok"


def test_valid_token_for_a_different_enabled_tier_is_still_rejected(db_session, org_id):
    token = _member_with_token(db_session, org_id, mcp_access=True, email="wrong-tier@acme.com")
    MCPSettingsService(MCPSettingsRepository(db_session)).update(org_id, True, False, False, None)
    db_session.commit()

    result = _service(db_session).test(org_id, "write", token)

    assert result.ok is False
    assert result.reason == "tier_disabled"
