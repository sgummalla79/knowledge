import asyncio
import json
from uuid import uuid4

import pytest
from mcp.server.fastmcp import FastMCP

from api.application.profile_service import ProfileService
from api.application.shelf_service import ShelfService
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.category_repository import CategoryRepository
from api.infrastructure.repositories.document_repository import DocumentRepository
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.infrastructure.repositories.shelf_repository import ShelfRepository
from api.infrastructure.repositories.tag_repository import TagRepository
from conftest import authenticate_as, enable_tier
from api.mcp_server.tools.write import register

# Each tool is a thin wrapper around the exact same *Service method the matching HTTP route calls
# — these are round-trip proofs that the wiring reaches the real service and respects the write
# tier's gates, not an exhaustive matrix (the services themselves are already covered by api/tests).


def _test_server() -> FastMCP:
    mcp = FastMCP(name="test-write")
    register(mcp)
    return mcp


def _call(server: FastMCP, name: str, arguments: dict):
    raw = asyncio.run(server.call_tool(name, arguments))
    if isinstance(raw, tuple):
        _content, structured = raw
        return structured.get("result", structured)
    if raw and raw[0].text:
        return json.loads(raw[0].text)
    return None


@pytest.fixture()
def org_id(db_session):
    organization = bootstrap_default_organization(db_session)
    profiles = ProfileRepository(db_session)
    if profiles.get_admin_profile(organization.id) is None:
        ProfileService(profiles).create_admin_profile(organization.id)
        db_session.commit()
    return organization.id


@pytest.fixture()
def writer(db_session, org_id):
    # A real identities.id row, not a bare uuid4() — create_document's start_ingestion writes
    # caller["identity_id"] into ingestion_jobs.triggered_by, a real FK.
    identity = IdentityRepository(db_session).create("writer@acme.com", "hashed", name="Writer")
    db_session.commit()
    authenticate_as(org_id, identity.id, ["documents:write", "categories:write", "shelves:write", "tags:write"])
    return identity.id


def test_write_tier_raises_when_disabled_for_org(db_session, org_id):
    # No enable_tier call — write tier off by default even though the caller's scope is granted.
    authenticate_as(org_id, uuid4(), ["categories:write"])
    server = _test_server()

    with pytest.raises(Exception):
        asyncio.run(server.call_tool("create_category", {"name": "Engineering"}))


def test_create_category_reaches_real_service(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
    server = _test_server()

    result = _call(server, "create_category", {"name": "Engineering", "description": "Eng docs"})

    assert result["name"] == "Engineering"
    stored = CategoryRepository(db_session).list_by_org(org_id)
    assert len(stored) == 1 and stored[0].name == "Engineering"


def test_update_and_delete_category_reach_real_service(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
    category = CategoryRepository(db_session).create(org_id, "Engineering", "engineering", description=None)
    db_session.commit()
    server = _test_server()

    updated = _call(server, "update_category", {"category_id": str(category.id), "name": "Eng"})
    assert updated["name"] == "Eng"

    _call(server, "delete_category", {"category_id": str(category.id)})
    assert CategoryRepository(db_session).list_by_org(org_id) == []


def test_create_shelf_and_add_remove_document_reach_real_service(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
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
    server = _test_server()

    shelf = _call(server, "create_shelf", {"name": "General"})
    assert shelf["name"] == "General"

    shelf_service = ShelfService(ShelfRepository(db_session))
    _call(server, "add_document_to_shelf", {"shelf_id": shelf["id"], "document_id": str(document.id)})
    assert shelf_service.document_count(shelf["id"]) == 1

    _call(server, "remove_document_from_shelf", {"shelf_id": shelf["id"], "document_id": str(document.id)})
    assert shelf_service.document_count(shelf["id"]) == 0

    _call(server, "delete_shelf", {"shelf_id": shelf["id"]})
    assert shelf_service.list_shelves(org_id) == []


def test_add_document_to_shelf_enforces_org_isolation(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
    other_identity = IdentityRepository(db_session).create("other-owner@acme.com", "hashed", name="Other Owner")
    other_org = OrganizationRepository(db_session).create("Other Org", "other-org")
    document = DocumentRepository(db_session).create(
        org_id=other_org.id,
        owner_id=other_identity.id,
        title="Not yours",
        type="document",
        file_type="md",
        content_hash="def456",
        content_uri=None,
        description=None,
        status="indexed",
    )
    db_session.commit()
    server = _test_server()

    shelf = _call(server, "create_shelf", {"name": "General"})

    with pytest.raises(Exception):
        asyncio.run(
            server.call_tool("add_document_to_shelf", {"shelf_id": shelf["id"], "document_id": str(document.id)})
        )


def test_create_tag_and_tag_untag_document_reach_real_service(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
    identity = IdentityRepository(db_session).create("owner2@acme.com", "hashed", name="Owner Two")
    document = DocumentRepository(db_session).create(
        org_id=org_id,
        owner_id=identity.id,
        title="Runbook 2",
        type="document",
        file_type="md",
        content_hash="ghi789",
        content_uri=None,
        description=None,
        status="indexed",
    )
    db_session.commit()
    server = _test_server()

    tag = _call(server, "create_tag", {"name": "urgent"})
    assert tag["name"] == "urgent"

    _call(server, "tag_document", {"document_id": str(document.id), "tag_id": tag["id"]})
    tag_repo = TagRepository(db_session)
    assert [t.name for t in tag_repo.list_for_document(document.id)] == ["urgent"]

    _call(server, "untag_document", {"document_id": str(document.id), "tag_id": tag["id"]})
    assert tag_repo.list_for_document(document.id) == []


def test_rename_and_delete_document_reach_real_service(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
    identity = IdentityRepository(db_session).create("owner3@acme.com", "hashed", name="Owner Three")
    document = DocumentRepository(db_session).create(
        org_id=org_id,
        owner_id=identity.id,
        title="Old title",
        type="document",
        file_type="md",
        content_hash="jkl012",
        content_uri=None,
        description=None,
        status="indexed",
    )
    db_session.commit()
    server = _test_server()

    renamed = _call(server, "rename_document", {"document_id": str(document.id), "title": "New title"})
    assert renamed["title"] == "New title"

    _call(server, "delete_document", {"document_id": str(document.id)})
    assert DocumentRepository(db_session).get(document.id) is None


def test_create_document_starts_a_real_ingestion_job(db_session, org_id, writer):
    enable_tier(db_session, org_id, write=True)
    server = _test_server()

    result = _call(server, "create_document", {"title": "Inline note", "content": "# Hello\n\nSome content."})

    assert isinstance(result["job_id"], str) and result["job_id"]
