import base64
import hashlib
import secrets
from uuid import uuid4

import pytest

from api.application.app_auth_service import AppAuthService
from api.application.application_service import ApplicationService
from api.application.oauth_authorization_service import OAuthAuthorizationService
from api.application.org_membership_service import OrgMembershipService
from api.application.permission_service import PermissionService
from api.application.profile_service import ProfileService
from api.domain.errors import AuthenticationError, ConflictError, ValidationError
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.application_oauth_client_repository import ApplicationOAuthClientRepository
from api.infrastructure.repositories.application_repository import ApplicationRepository
from api.infrastructure.repositories.authorization_code_repository import AuthorizationCodeRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.infrastructure.repositories.refresh_token_repository import RefreshTokenRepository


@pytest.fixture()
def org_id(db_session):
    organization = bootstrap_default_organization(db_session)
    profiles = ProfileRepository(db_session)
    if profiles.get_admin_profile(organization.id) is None:
        ProfileService(profiles).create_admin_profile(organization.id)
        db_session.commit()
    return organization.id


def _service(db_session) -> ApplicationService:
    return ApplicationService(
        ApplicationRepository(db_session),
        IdentityRepository(db_session),
        OrgMemberRepository(db_session),
        ProfileRepository(db_session),
        ApplicationOAuthClientRepository(db_session),
    )


def _auth_service(db_session) -> AppAuthService:
    return AppAuthService(
        ApplicationRepository(db_session),
        PersonalAccessTokenRepository(db_session),
        PermissionService(OrgMemberRepository(db_session), ProfileRepository(db_session)),
    )


def _oauth_service(db_session) -> OAuthAuthorizationService:
    return OAuthAuthorizationService(
        ApplicationRepository(db_session),
        ApplicationOAuthClientRepository(db_session),
        AuthorizationCodeRepository(db_session),
        RefreshTokenRepository(db_session),
    )


def _member_with_profile(db_session, org_id, permissions, email):
    identity = IdentityRepository(db_session).create(email, "hashed", name=email)
    db_session.commit()
    profile, _ = ProfileService(ProfileRepository(db_session)).create(org_id, f"profile-{email}", None, permissions, None)
    db_session.commit()
    org_service = OrgMembershipService(
        OrganizationRepository(db_session), OrgMemberRepository(db_session), IdentityRepository(db_session), ProfileRepository(db_session)
    )
    org_service.invite_member(org_id, email, profile.id, None)
    db_session.commit()
    return identity


def test_update_renames_application(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "rename@acme.com")
    service = _service(db_session)
    application, _ = service.create_client_credentials(org_id, "CI robot", None, member.id, None)
    db_session.commit()

    updated = service.update(org_id, application.id, "CI robot renamed", "new description")
    db_session.commit()

    assert updated.name == "CI robot renamed"
    assert updated.description == "new description"
    assert service.get(org_id, application.id).name == "CI robot renamed"


# ── oauth_client_credentials ─────────────────────────────────────────────────────────────────


def test_create_client_credentials_rejects_non_member_execute_as_identity(db_session, org_id):
    service = _service(db_session)

    with pytest.raises(ValidationError):
        service.create_client_credentials(org_id, "CI robot", None, uuid4(), None)


def test_create_client_credentials_duplicate_name_in_same_org_conflicts(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "dup@acme.com")
    service = _service(db_session)
    service.create_client_credentials(org_id, "CI robot", None, member.id, None)
    db_session.commit()

    with pytest.raises(ConflictError):
        service.create_client_credentials(org_id, "CI robot", None, member.id, None)


def test_create_client_credentials_mcp_access_defaults_to_false_and_persists_when_set(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "mcp@acme.com")
    service = _service(db_session)

    default_app, _ = service.create_client_credentials(org_id, "CI robot", None, member.id, None)
    mcp_app, mcp_raw_secret = service.create_client_credentials(org_id, "MCP robot", None, member.id, None, mcp_access=True)
    db_session.commit()

    assert default_app.mcp_access is False
    assert mcp_app.mcp_access is True
    assert ApplicationRepository(db_session).get(mcp_app.id).mcp_access is True

    # ResolvedCaller carries mcp_access through too — the gate api/mcp_server/permissions.py's
    # require_tier_permission will consult.
    access_token = _oauth_service(db_session).issue_client_credentials_token(mcp_app.id, mcp_raw_secret)
    caller = _auth_service(db_session).authenticate_bearer_token(access_token)
    assert caller.mcp_access is True


def test_client_credentials_token_resolves_to_execute_as_profile_end_to_end(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "readonly@acme.com")
    service = _service(db_session)

    application, raw_secret = service.create_client_credentials(org_id, "CI robot", None, member.id, None)
    db_session.commit()

    oauth_service = _oauth_service(db_session)
    access_token = oauth_service.issue_client_credentials_token(application.id, raw_secret)

    auth_service = _auth_service(db_session)
    caller = auth_service.authenticate_bearer_token(access_token)
    assert caller.org_id == org_id
    assert caller.identity_id == member.id
    assert caller.scopes == frozenset({"documents:read"})

    # Wrong secret is rejected the same way as an unknown client.
    with pytest.raises(AuthenticationError):
        oauth_service.issue_client_credentials_token(application.id, "wrong-secret")


def test_revoking_client_credentials_application_invalidates_issued_token(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "readonly2@acme.com")
    service = _service(db_session)
    application, raw_secret = service.create_client_credentials(org_id, "CI robot", None, member.id, None)
    db_session.commit()

    oauth_service = _oauth_service(db_session)
    access_token = oauth_service.issue_client_credentials_token(application.id, raw_secret)

    service.revoke(org_id, application.id, None)
    db_session.commit()

    auth_service = _auth_service(db_session)
    assert auth_service.authenticate_bearer_token(access_token) is None


def test_rotate_client_secret_invalidates_the_old_secret(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "readonly3@acme.com")
    service = _service(db_session)
    application, old_secret = service.create_client_credentials(org_id, "CI robot", None, member.id, None)
    db_session.commit()

    _, new_secret = service.rotate_client_secret(org_id, application.id)
    db_session.commit()

    oauth_service = _oauth_service(db_session)
    with pytest.raises(AuthenticationError):
        oauth_service.issue_client_credentials_token(application.id, old_secret)
    assert oauth_service.issue_client_credentials_token(application.id, new_secret) is not None


# ── oauth_authorization_code ─────────────────────────────────────────────────────────────────

_REDIRECT_URI = "http://127.0.0.1:9999/callback"


def _pkce_pair():
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def test_create_authorization_code_client_rejects_empty_redirect_uris(db_session, org_id):
    service = _service(db_session)

    with pytest.raises(ValidationError):
        service.create_authorization_code_client(org_id, "MCP client", None, [], None)


def test_create_authorization_code_client_has_no_org_membership_for_its_placeholder_identity(db_session, org_id):
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    assert OrgMemberRepository(db_session).get(org_id, application.service_identity_id) is None


def test_authorization_code_flow_resolves_to_consenting_member_profile_end_to_end(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "consenting@acme.com")
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    verifier, challenge = _pkce_pair()
    oauth_service = _oauth_service(db_session)
    code = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge, "")
    db_session.commit()

    access_token, refresh_token = oauth_service.exchange_authorization_code(code, _REDIRECT_URI, application.id, verifier)
    db_session.commit()
    assert refresh_token is None

    caller = _auth_service(db_session).authenticate_bearer_token(access_token)
    assert caller.identity_id == member.id
    assert caller.org_id == org_id
    assert caller.scopes == frozenset({"documents:read"})


def test_authorization_code_cannot_be_reused(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "reuse@acme.com")
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    verifier, challenge = _pkce_pair()
    oauth_service = _oauth_service(db_session)
    code = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge, "")
    db_session.commit()
    oauth_service.exchange_authorization_code(code, _REDIRECT_URI, application.id, verifier)
    db_session.commit()

    with pytest.raises(ValidationError):
        oauth_service.exchange_authorization_code(code, _REDIRECT_URI, application.id, verifier)


def test_authorization_code_redirect_uri_mismatch_at_exchange_fails(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "mismatch@acme.com")
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    verifier, challenge = _pkce_pair()
    oauth_service = _oauth_service(db_session)
    code = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge, "")
    db_session.commit()

    with pytest.raises(ValidationError):
        oauth_service.exchange_authorization_code(code, "http://127.0.0.1:9999/different-path", application.id, verifier)


def test_authorization_code_wrong_pkce_verifier_fails(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "wrongpkce@acme.com")
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    _, challenge = _pkce_pair()
    oauth_service = _oauth_service(db_session)
    code = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge, "")
    db_session.commit()

    with pytest.raises(ValidationError):
        oauth_service.exchange_authorization_code(code, _REDIRECT_URI, application.id, "wrong-verifier")


def test_registered_redirect_uri_matches_a_different_loopback_port(db_session, org_id):
    application = _service(db_session).create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    _, oauth_client = _oauth_service(db_session).get_authorization_code_client(application.id)

    # Should not raise even though the port differs — RFC 8252 §7.3's loopback exemption.
    _oauth_service(db_session).validate_redirect_uri(oauth_client, "http://127.0.0.1:54321/callback")
    with pytest.raises(AuthenticationError):
        _oauth_service(db_session).validate_redirect_uri(oauth_client, "http://evil.example.com/callback")


def test_offline_access_scope_issues_refresh_token_that_reflects_a_later_profile_change(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "offline@acme.com")
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    verifier, challenge = _pkce_pair()
    oauth_service = _oauth_service(db_session)
    code = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge, "offline_access")
    db_session.commit()
    _, refresh_token = oauth_service.exchange_authorization_code(code, _REDIRECT_URI, application.id, verifier)
    db_session.commit()
    assert refresh_token is not None

    # A profile edit made after the original exchange is reflected on the very next refresh —
    # nothing about the member's permissions was baked into the refresh token itself.
    membership = OrgMemberRepository(db_session).get(org_id, member.id)
    ProfileService(ProfileRepository(db_session)).update(
        org_id, membership.profile_id, "profile-offline", None, ["documents:read", "categories:read"]
    )
    db_session.commit()

    new_access_token = oauth_service.refresh_access_token(refresh_token, application.id)
    caller = _auth_service(db_session).authenticate_bearer_token(new_access_token)
    assert caller.scopes == frozenset({"documents:read", "categories:read"})


def test_revoking_authorization_code_application_blocks_refresh_and_new_exchanges(db_session, org_id):
    member = _member_with_profile(db_session, org_id, ["documents:read"], "revoke-auth@acme.com")
    service = _service(db_session)
    application = service.create_authorization_code_client(org_id, "MCP client", None, [_REDIRECT_URI], None)
    db_session.commit()

    verifier, challenge = _pkce_pair()
    oauth_service = _oauth_service(db_session)
    code = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge, "offline_access")
    db_session.commit()
    _, refresh_token = oauth_service.exchange_authorization_code(code, _REDIRECT_URI, application.id, verifier)
    db_session.commit()

    service.revoke(org_id, application.id, None)
    db_session.commit()

    with pytest.raises(ValidationError):
        oauth_service.refresh_access_token(refresh_token, application.id)

    verifier2, challenge2 = _pkce_pair()
    code2 = oauth_service.create_authorization_code(application.id, org_id, member.id, _REDIRECT_URI, challenge2, "")
    db_session.commit()
    with pytest.raises(ValidationError):
        oauth_service.exchange_authorization_code(code2, _REDIRECT_URI, application.id, verifier2)
