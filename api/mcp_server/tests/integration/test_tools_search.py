import asyncio
import json
from uuid import uuid4

import pytest
from mcp.server.fastmcp import FastMCP

from api.application.profile_service import ProfileService
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from conftest import authenticate_as, enable_tier
from api.mcp_server.tools.search import register

# Calls the real registered tools via FastMCP.call_tool — not a refactored internal function — so
# this exercises the exact require_tier_permission + repository wiring a live MCP client would hit.


def _test_server() -> FastMCP:
    mcp = FastMCP(name="test-search")
    register(mcp)
    return mcp


def _call(server: FastMCP, name: str, arguments: dict):
    # call_tool(..., convert_result=True) returns (content_blocks, structured_output) when a
    # structured output schema could be inferred (list[dict] return types), or just the bare
    # content_blocks otherwise (plain `dict` return types) — a real client only ever consumes the
    # content blocks' JSON text either way, so tests normalize to that.
    raw = asyncio.run(server.call_tool(name, arguments))
    if isinstance(raw, tuple):
        _content, structured = raw
        return structured.get("result", structured)
    return json.loads(raw[0].text)


@pytest.fixture()
def org_id(db_session):
    organization = bootstrap_default_organization(db_session)
    profiles = ProfileRepository(db_session)
    if profiles.get_admin_profile(organization.id) is None:
        ProfileService(profiles).create_admin_profile(organization.id)
        db_session.commit()
    return organization.id


def test_list_categories_returns_only_this_orgs_categories(db_session, org_id):
    CategoryRepository(db_session).create(org_id, "Engineering", "engineering", description=None)
    db_session.commit()
    enable_tier(db_session, org_id, search=True)

    authenticate_as(org_id, uuid4(), ["categories:read"])
    server = _test_server()

    result = _call(server, "list_categories", {})

    assert len(result) == 1
    assert result[0]["name"] == "Engineering"


def test_list_categories_without_permission_raises(db_session, org_id):
    CategoryRepository(db_session).create(org_id, "Engineering", "engineering", description=None)
    db_session.commit()
    enable_tier(db_session, org_id, search=True)

    authenticate_as(org_id, uuid4(), ["documents:read"])  # categories:read not granted
    server = _test_server()

    with pytest.raises(Exception):
        asyncio.run(server.call_tool("list_categories", {}))


def test_list_categories_raises_when_search_tier_disabled_for_org():
    org_id = uuid4()
    authenticate_as(org_id, uuid4(), ["categories:read"])  # no enable_tier call — tier off by default
    server = _test_server()

    with pytest.raises(Exception):
        asyncio.run(server.call_tool("list_categories", {}))


def test_list_categories_raises_when_application_lacks_mcp_access(db_session, org_id):
    enable_tier(db_session, org_id, search=True)
    authenticate_as(org_id, uuid4(), ["categories:read"], mcp_access=False)
    server = _test_server()

    with pytest.raises(Exception):
        asyncio.run(server.call_tool("list_categories", {}))


def test_get_document_enforces_org_isolation(db_session, org_id):
    identity = IdentityRepository(db_session).create("owner@acme.com", "hashed", name="Owner")
    document = DocumentRepository(db_session).create(
        org_id=org_id,
        owner_id=identity.id,
        title="Runbook",
        type="document",
        file_type="md",
        content_hash="abc123",
        content_uri=None,
        description=None,
        status="indexed",
    )
    db_session.commit()
    enable_tier(db_session, org_id, search=True)

    authenticate_as(uuid4(), uuid4(), ["documents:read"])  # a different, unrelated org
    server = _test_server()

    with pytest.raises(Exception):
        asyncio.run(server.call_tool("get_document", {"document_id": str(document.id)}))

    # The real owning org can fetch it.
    authenticate_as(org_id, identity.id, ["documents:read"])
    result = _call(server, "get_document", {"document_id": str(document.id)})
    assert result["title"] == "Runbook"
