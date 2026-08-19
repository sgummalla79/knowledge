from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import Identity, OrgMember, Organization
from api.domain.errors import ConflictError, ForbiddenError, NotFoundError

# HTTP-layer wiring only (status codes, headers, error envelope) — services are mocked. `orgs.py`
# had zero dedicated test coverage before this file; added alongside the new PATCH /orgs/<id>
# route (A.8) rather than deferred, since the route file was already being touched.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["active_role"] = "admin"
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
        role="admin",
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
        email="ada@acme.com",
        name="Ada Lovelace",
        password_hash="hashed",
        must_change_password=False,
        created_at=now,
        last_modified_at=now,
        last_active_at=None,
    )
    fields.update(overrides)
    return Identity(**fields)


def test_list_orgs_returns_memberships(client):
    org = _org()
    member = _member(org_id=org.id, role="admin")
    with (
        patch("api.presentation.routes.orgs.OrganizationRepository.get", return_value=org),
        patch("api.presentation.routes.orgs.OrgMemberRepository.list_for_identity", return_value=[member]),
    ):
        response = client.get("/orgs")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["id"] == str(org.id)
    assert body[0]["role"] == "admin"


def test_create_org_returns_201(client):
    org = _org()
    with patch(
        "api.presentation.routes.orgs.OrgMembershipService.create_org_with_owner", return_value=org
    ):
        response = client.post("/orgs", json={"name": "Acme Corp"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["name"] == "Acme Corp"
    assert body["role"] == "admin"


def test_create_org_missing_name_returns_structured_400(client):
    response = client.post("/orgs", json={})

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "name"


def test_create_org_duplicate_slug_returns_409(client):
    with patch(
        "api.presentation.routes.orgs.OrgMembershipService.create_org_with_owner",
        side_effect=ConflictError("organization_slug_taken", "already exists", field="slug"),
    ):
        response = client.post("/orgs", json={"name": "dup"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "organization_slug_taken"


def test_update_org_returns_updated_org(client):
    org = _org(name="renamed", description="new description")
    with (
        patch("api.presentation.routes.orgs._require_admin", return_value=None),
        patch(
            "api.presentation.routes.orgs.OrgMembershipService.update_organization", return_value=org
        ),
    ):
        response = client.patch(
            f"/orgs/{org.id}", json={"name": "renamed", "description": "new description"}
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "renamed"
    assert body["description"] == "new description"


def test_update_org_requires_admin(client):
    with patch(
        "api.presentation.routes.orgs._require_admin",
        side_effect=ForbiddenError("Only an org admin can manage members."),
    ):
        response = client.patch(f"/orgs/{uuid4()}", json={"name": "renamed"})

    assert response.status_code == 403


def test_update_org_missing_name_returns_structured_400(client):
    with patch("api.presentation.routes.orgs._require_admin", return_value=None):
        response = client.patch(f"/orgs/{uuid4()}", json={"description": "no name"})

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "name"


def test_update_missing_org_returns_structured_404(client):
    with (
        patch("api.presentation.routes.orgs._require_admin", return_value=None),
        patch(
            "api.presentation.routes.orgs.OrgMembershipService.update_organization",
            side_effect=NotFoundError("organization_not_found", "Organization not found."),
        ),
    ):
        response = client.patch(f"/orgs/{uuid4()}", json={"name": "renamed"})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "organization_not_found"


def test_switch_org_updates_session(client):
    with patch(
        "api.presentation.routes.orgs.OrgMembershipService.switch_active_org", return_value="contributor"
    ):
        response = client.post(f"/orgs/{uuid4()}/switch")

    assert response.status_code == 200
    assert response.get_json()["role"] == "contributor"


def test_switch_org_not_a_member_returns_structured_404(client):
    with patch(
        "api.presentation.routes.orgs.OrgMembershipService.switch_active_org",
        side_effect=NotFoundError("not_an_org_member", "You are not a member of this organization."),
    ):
        response = client.post(f"/orgs/{uuid4()}/switch")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_an_org_member"


def test_list_members_returns_all(client):
    identity = _identity()
    member = _member(identity_id=identity.id)
    with patch(
        "api.presentation.routes.orgs.OrgMembershipService.list_members", return_value=[(member, identity)]
    ):
        response = client.get(f"/orgs/{uuid4()}/members")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["email"] == "ada@acme.com"


def test_invite_member_requires_admin(client):
    with patch(
        "api.presentation.routes.orgs._require_admin",
        side_effect=ForbiddenError("Only an org admin can manage members."),
    ):
        response = client.post(f"/orgs/{uuid4()}/invites", json={"email": "new@acme.com"})

    assert response.status_code == 403


def test_invite_member_returns_201(client):
    identity = _identity(email="new@acme.com")
    member = _member(identity_id=identity.id, role="viewer")
    with (
        patch("api.presentation.routes.orgs._require_admin", return_value=None),
        patch("api.presentation.routes.orgs.OrgMembershipService.invite_member", return_value=member),
        patch("api.presentation.routes.orgs.IdentityRepository.get_by_id", return_value=identity),
    ):
        response = client.post(f"/orgs/{uuid4()}/invites", json={"email": "new@acme.com"})

    assert response.status_code == 201
    assert response.get_json()["email"] == "new@acme.com"


def test_update_member_role_requires_admin(client):
    with patch(
        "api.presentation.routes.orgs._require_admin",
        side_effect=ForbiddenError("Only an org admin can manage members."),
    ):
        response = client.patch(f"/orgs/{uuid4()}/members/{uuid4()}", json={"role": "admin"})

    assert response.status_code == 403


def test_update_member_role_returns_updated_member(client):
    identity = _identity()
    member = _member(identity_id=identity.id, role="admin")
    with (
        patch("api.presentation.routes.orgs._require_admin", return_value=None),
        patch("api.presentation.routes.orgs.OrgMembershipService.update_role", return_value=member),
        patch("api.presentation.routes.orgs.IdentityRepository.get_by_id", return_value=identity),
    ):
        response = client.patch(f"/orgs/{uuid4()}/members/{identity.id}", json={"role": "admin"})

    assert response.status_code == 200
    assert response.get_json()["role"] == "admin"


def test_remove_member_requires_admin(client):
    with patch(
        "api.presentation.routes.orgs._require_admin",
        side_effect=ForbiddenError("Only an org admin can manage members."),
    ):
        response = client.delete(f"/orgs/{uuid4()}/members/{uuid4()}")

    assert response.status_code == 403


def test_remove_member_returns_204(client):
    with (
        patch("api.presentation.routes.orgs._require_admin", return_value=None),
        patch("api.presentation.routes.orgs.OrgMembershipService.remove_member", return_value=None),
    ):
        response = client.delete(f"/orgs/{uuid4()}/members/{uuid4()}")

    assert response.status_code == 204
