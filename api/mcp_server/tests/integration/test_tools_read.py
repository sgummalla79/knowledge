import asyncio
import json
from uuid import uuid4

import pytest
from mcp.server.fastmcp import FastMCP

from api.application.profile_service import ProfileService
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.infrastructure.repositories.tag_repository import TagRepository
from conftest import authenticate_as, enable_tier
from api.mcp_server.tools.read import register


def _test_server() -> FastMCP:
    mcp = FastMCP(name="test-read")
    register(mcp)
    return mcp


def _call(server: FastMCP, name: str, arguments: dict):
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


def test_list_shelves_returns_org_shelves(db_session, org_id):
    ShelfRepository(db_session).create(org_id, "General", "general", description=None, is_default=True)
    db_session.commit()
    enable_tier(db_session, org_id, read=True)

    authenticate_as(org_id, uuid4(), ["shelves:read"])
    server = _test_server()

    result = _call(server, "list_shelves", {})

    assert len(result) == 1
    assert result[0]["name"] == "General"


def test_list_shelves_raises_when_read_tier_disabled_for_org(db_session, org_id):
    ShelfRepository(db_session).create(org_id, "General", "general", description=None, is_default=True)
    db_session.commit()
    # No enable_tier call — read tier off by default even though the caller's scope is granted.

    authenticate_as(org_id, uuid4(), ["shelves:read"])
    server = _test_server()

    with pytest.raises(Exception):
        asyncio.run(server.call_tool("list_shelves", {}))


def test_list_tags_returns_org_tags(db_session, org_id):
    TagRepository(db_session).create(org_id, name="urgent")
    db_session.commit()
    enable_tier(db_session, org_id, read=True)

    authenticate_as(org_id, uuid4(), ["tags:read"])
    server = _test_server()

    result = _call(server, "list_tags", {})

    assert len(result) == 1
    assert result[0]["name"] == "urgent"


def test_list_embedding_models_returns_known_providers(db_session, org_id):
    enable_tier(db_session, org_id, read=True)

    authenticate_as(org_id, uuid4(), ["embedding_models:read"])
    server = _test_server()

    result = _call(server, "list_embedding_models", {})

    assert isinstance(result, list)
    assert len(result) > 0
    assert all("provider" in status for status in result)
