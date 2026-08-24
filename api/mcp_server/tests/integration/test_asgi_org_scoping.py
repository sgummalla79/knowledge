import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from api.application.personal_access_token_service import PersonalAccessTokenService
from api.application.profile_service import ProfileService
from api.infrastructure.auth.passwords import hash_password
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.personal_access_token_repository import PersonalAccessTokenRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.presentation.web.mcp_org_scoping import MCPOrgScopingMiddleware

# _patch_session_local (autouse, from this directory's conftest.py) points mcp_org_scoping.py's
# session_scope() at the same testcontainers DB db_session uses, so the middleware's own DB lookups
# see whatever a test sets up via db_session directly.


async def _echo(request):
    return PlainTextResponse(request.url.path)


async def _echo_caller(request):
    """Stands in for a tool call reading mcp_server/permissions.py's current_caller() — proves the
    middleware itself sets auth_context_var (FastMCP no longer does, see server.py), and that it's
    reset once the request completes rather than leaking into whatever handles the next one."""
    access_token = auth_context_var.get().access_token
    return PlainTextResponse(f"{access_token.claims['org_id']}:{access_token.claims['mcp_access']}")


def _dummy_downstream_app() -> Starlette:
    """Stands in for the real FastMCP-mounted app — the middleware under test only cares about
    rejecting/rewriting before a request reaches whatever's downstream, not about MCP protocol
    specifics, so a trivial app that echoes back the path it received is enough to prove the
    rewrite happened."""
    return Starlette(routes=[Route("/mcp/{tier}", _echo), Route("/mcp/{tier}/whoami", _echo_caller)])


@pytest.fixture()
def client():
    app = MCPOrgScopingMiddleware(_dummy_downstream_app())
    return TestClient(app)


def _org_with_token(db_session, slug="acme-labs", mcp_access=True):
    identity = IdentityRepository(db_session).create(
        f"{slug}-owner@acme.com", hash_password("irrelevant"), name="Owner"
    )
    organization = OrganizationRepository(db_session).create(
        slug, slug, created_by=identity.id, last_modified_by=identity.id
    )
    profile_service = ProfileService(ProfileRepository(db_session))
    admin_profile = profile_service.create_admin_profile(organization.id, identity.id)
    OrgMemberRepository(db_session).create(organization.id, identity.id, admin_profile.id)
    _token_entity, raw_token = PersonalAccessTokenService(PersonalAccessTokenRepository(db_session)).create(
        organization.id, identity.id, "test token", mcp_access=mcp_access
    )
    db_session.commit()
    return organization, raw_token


def test_non_mcp_path_passes_through_untouched(client):
    response = client.get("/health")
    assert response.status_code == 404  # no such route on the dummy downstream app either
    # ...but crucially it reached the downstream app at all, rather than being rejected by the
    # middleware's own logic — a 404 from Starlette's own router, not from mcp_org_scoping.


def test_bare_mcp_path_is_rejected(client):
    response = client.get("/mcp/search")
    assert response.status_code == 404


def test_missing_bearer_token_is_rejected(db_session, client):
    org, _token = _org_with_token(db_session)
    response = client.get(f"/{org.slug}/mcp/search")
    assert response.status_code == 401


def test_unknown_org_slug_is_rejected(db_session, client):
    _org, token = _org_with_token(db_session)
    response = client.get("/no-such-org/mcp/search", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_token_for_a_different_org_is_rejected(db_session, client):
    org_a, _token_a = _org_with_token(db_session, slug="org-a")
    _org_b, token_b = _org_with_token(db_session, slug="org-b")
    response = client.get(f"/{org_a.slug}/mcp/search", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 403


def test_matching_org_and_token_forwards_with_rewritten_path(db_session, client):
    org, token = _org_with_token(db_session)
    response = client.get(f"/{org.slug}/mcp/search", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.text == "/mcp/search"


def test_matching_org_and_token_forwards_a_sub_path(db_session, client):
    org, token = _org_with_token(db_session)
    response = client.get(f"/{org.slug}/mcp/write", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.text == "/mcp/write"


def test_forwarded_request_carries_the_resolved_caller_via_auth_context_var(db_session, client):
    org, token = _org_with_token(db_session)
    response = client.get(f"/{org.slug}/mcp/search/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.text == f"{org.id}:True"


def test_auth_context_var_is_reset_after_the_request_completes(db_session, client):
    org, token = _org_with_token(db_session)
    client.get(f"/{org.slug}/mcp/search", headers={"Authorization": f"Bearer {token}"})
    assert auth_context_var.get() is None


def test_unhandled_exception_resolving_org_scope_returns_500_and_is_logged(db_session, client, caplog, monkeypatch):
    """This middleware sits entirely outside Flask's own @app.errorhandler(Exception) -- a DB or
    lookup failure here must not escape raw and unlogged straight to uvicorn."""
    org, token = _org_with_token(db_session)

    def _boom(self, slug):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(OrganizationRepository, "get_by_slug", _boom)

    with caplog.at_level("ERROR", logger="api.presentation.web.mcp_org_scoping"):
        response = client.get(f"/{org.slug}/mcp/search", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "An unexpected error occurred."
    assert any("Unhandled exception resolving MCP org scope" in record.message for record in caplog.records)
