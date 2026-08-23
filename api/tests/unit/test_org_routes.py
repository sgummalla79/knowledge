from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Identity, OrgMember, Organization, Profile, Shelf
from api.domain.errors import AuthenticationError

# HTTP-layer wiring only (status codes, headers, error envelope) — services are mocked. The global
# _grant_every_permission fixture (unit/conftest.py) means every request here already has every
# permission unless a test overrides it locally to verify a denial.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    test_client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
    return test_client


def _org(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        name="Acme Corp",
        slug="acme-corp",
        description=None,
        plan="free",
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Organization(**fields)


def _member(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        identity_id=uuid4(),
        profile_id=uuid4(),
        invited_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return OrgMember(**fields)


def _identity(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        username="ada@acme.com",
        email=None,
        name="Ada Lovelace",
        password_hash="hashed",
        must_change_password=False,
        created_at=now,
        last_modified_at=now,
        last_active_at=None,
    )
    fields.update(overrides)
    return Identity(**fields)


def _profile(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="Admin",
        description=None,
        is_admin=True,
        is_system=True,
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Profile(**fields)


def test_list_orgs_returns_memberships(client):
    org = _org()
    member = _member(org_id=org.id)
    with (
        patch("api.presentation.routes.orgs.OrganizationRepository.get", return_value=org),
        patch("api.presentation.routes.orgs.OrgMemberRepository.list_for_identity", return_value=[member]),
    ):
        response = client.get("/orgs")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["id"] == str(org.id)
    assert "applications:write" in body[0]["permissions"]


def test_get_me_returns_own_account_and_profile(client):
    identity = _identity(username="me@acme.com", email="me@acme.com")
    profile = _profile(name="Contributor", is_admin=False)
    member = _member(identity_id=identity.id, profile_id=profile.id)
    with (
        patch("api.presentation.routes.orgs.OrgMemberRepository.get", return_value=member),
        patch("api.presentation.routes.orgs.IdentityRepository.get_by_id", return_value=identity),
        patch("api.presentation.routes.orgs.ProfileRepository.get", return_value=profile),
    ):
        response = client.get("/orgs/me")

    assert response.status_code == 200
    body = response.get_json()
    assert body["username"] == "me@acme.com"
    assert body["profile_name"] == "Contributor"
    assert body["profile_is_admin"] is False


def test_update_me_returns_updated_account(client):
    identity = _identity(username="me@acme.com", email="new-email@acme.com", name="New Name")
    profile = _profile(name="Contributor", is_admin=False)
    member = _member(identity_id=identity.id, profile_id=profile.id)
    with (
        patch("api.presentation.routes.orgs.AuthService.update_profile", return_value=identity),
        patch("api.presentation.routes.orgs.OrgMemberRepository.get", return_value=member),
        patch("api.presentation.routes.orgs.ProfileRepository.get", return_value=profile),
    ):
        response = client.patch("/orgs/me", json={"name": "New Name", "email": "new-email@acme.com"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "New Name"
    assert body["email"] == "new-email@acme.com"


def test_update_me_username_returns_updated_account(client):
    identity = _identity(username="new-username@acme.com")
    profile = _profile()
    member = _member(identity_id=identity.id, profile_id=profile.id)
    with (
        patch("api.presentation.routes.orgs.AuthService.change_username", return_value=identity),
        patch("api.presentation.routes.orgs.OrgMemberRepository.get", return_value=member),
        patch("api.presentation.routes.orgs.ProfileRepository.get", return_value=profile),
    ):
        response = client.patch(
            "/orgs/me/username",
            json={"username": "new-username@acme.com", "current_password": "correct-password"},
        )

    assert response.status_code == 200
    assert response.get_json()["username"] == "new-username@acme.com"


def test_update_me_username_wrong_password_returns_401(client):
    with patch(
        "api.presentation.routes.orgs.AuthService.change_username",
        side_effect=AuthenticationError("Incorrect password."),
    ):
        response = client.patch(
            "/orgs/me/username", json={"username": "new-username@acme.com", "current_password": "wrong"}
        )

    assert response.status_code == 401


def test_update_organization_returns_updated_org(client):
    org = _org(name="acme-renamed", slug="acme-renamed")
    with patch("api.presentation.routes.orgs.OrgMembershipService.change_organization_name", return_value=org):
        response = client.patch(f"/orgs/{org.id}", json={"name": "acme-renamed", "current_password": "correct-password"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "acme-renamed"
    assert body["slug"] == "acme-renamed"


def test_update_organization_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.patch(f"/orgs/{uuid4()}", json={"name": "acme-renamed", "current_password": "pw"})

    assert response.status_code == 403


def test_update_organization_wrong_password_returns_401(client):
    with patch(
        "api.presentation.routes.orgs.OrgMembershipService.change_organization_name",
        side_effect=AuthenticationError("Incorrect password."),
    ):
        response = client.patch(f"/orgs/{uuid4()}", json={"name": "acme-renamed", "current_password": "wrong"})

    assert response.status_code == 401


def test_list_members_returns_all(client):
    identity = _identity()
    profile = _profile()
    member = _member(identity_id=identity.id, profile_id=profile.id)
    with (
        patch("api.presentation.routes.orgs.OrgMembershipService.list_members", return_value=[(member, identity)]),
        patch("api.presentation.routes.orgs.ProfileRepository.get", return_value=profile),
    ):
        response = client.get(f"/orgs/{uuid4()}/members")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["username"] == "ada@acme.com"
    assert body[0]["profile_name"] == "Admin"
    assert body[0]["profile_is_admin"] is True


def test_list_members_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.get(f"/orgs/{uuid4()}/members")

    assert response.status_code == 403


def test_invite_member_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.post(f"/orgs/{uuid4()}/invites", json={"email": "new@acme.com", "profile_id": str(uuid4())})

    assert response.status_code == 403


def test_invite_member_returns_201(client):
    identity = _identity(username="new@acme.com", email="new@acme.com")
    profile = _profile(name="Viewer", is_admin=False)
    member = _member(identity_id=identity.id, profile_id=profile.id)
    with (
        patch("api.presentation.routes.orgs.OrgMembershipService.invite_member", return_value=member),
        patch("api.presentation.routes.orgs.IdentityRepository.get_by_id", return_value=identity),
        patch("api.presentation.routes.orgs.ProfileRepository.get", return_value=profile),
    ):
        response = client.post(f"/orgs/{uuid4()}/invites", json={"email": "new@acme.com", "profile_id": str(profile.id)})

    assert response.status_code == 201
    assert response.get_json()["username"] == "new@acme.com"
    assert response.get_json()["profile_name"] == "Viewer"


def test_update_member_profile_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.patch(f"/orgs/{uuid4()}/members/{uuid4()}", json={"profile_id": str(uuid4())})

    assert response.status_code == 403


def test_update_member_profile_returns_updated_member(client):
    identity = _identity()
    profile = _profile()
    member = _member(identity_id=identity.id, profile_id=profile.id)
    with (
        patch("api.presentation.routes.orgs.OrgMembershipService.update_member_profile", return_value=member),
        patch("api.presentation.routes.orgs.IdentityRepository.get_by_id", return_value=identity),
        patch("api.presentation.routes.orgs.ProfileRepository.get", return_value=profile),
    ):
        response = client.patch(f"/orgs/{uuid4()}/members/{identity.id}", json={"profile_id": str(profile.id)})

    assert response.status_code == 200
    assert response.get_json()["profile_id"] == str(profile.id)


def test_remove_member_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.delete(f"/orgs/{uuid4()}/members/{uuid4()}")

    assert response.status_code == 403


def test_remove_member_returns_204(client):
    with patch("api.presentation.routes.orgs.OrgMembershipService.remove_member", return_value=None):
        response = client.delete(f"/orgs/{uuid4()}/members/{uuid4()}")

    assert response.status_code == 204


def _shelf(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="Engineering",
        slug="engineering",
        description=None,
        is_default=False,
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Shelf(**fields)


def test_get_member_shelf_access_requires_permission(client):
    with patch("api.presentation.routes.app_auth.PermissionService.resolve_permissions", return_value=frozenset()):
        response = client.get(f"/orgs/{uuid4()}/members/{uuid4()}/shelf-access")

    assert response.status_code == 403


def test_get_member_shelf_access_returns_shelves(client):
    shelf = _shelf()
    with patch("api.presentation.routes.orgs.ShelfService.list_accessible_shelves", return_value=[shelf]):
        response = client.get(f"/orgs/{uuid4()}/members/{uuid4()}/shelf-access")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["name"] == "Engineering"
