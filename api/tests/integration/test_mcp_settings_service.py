import pytest

from api.application.mcp_settings_service import MCPSettingsService
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.mcp_settings_repository import MCPSettingsRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository


@pytest.fixture()
def org_id(db_session):
    return bootstrap_default_organization(db_session).id


@pytest.fixture()
def identity_id(db_session):
    # last_modified_by is a real FK to identities.id, unlike most other test callers that pass a
    # bare uuid4() for a caller not actually checked against the DB.
    return IdentityRepository(db_session).create("mcp-settings-tester@acme.com", "hashed", name="Tester").id


def _service(db_session) -> MCPSettingsService:
    return MCPSettingsService(MCPSettingsRepository(db_session))


def test_get_defaults_to_all_tiers_off_when_no_row_exists(db_session, org_id):
    settings = _service(db_session).get(org_id)

    assert settings.org_id == org_id
    assert settings.search_read_enabled is False
    assert settings.object_read_enabled is False
    assert settings.object_write_enabled is False


def test_update_persists_and_get_reflects_it(db_session, org_id, identity_id):
    service = _service(db_session)

    updated = service.update(org_id, True, True, False, identity_id)
    db_session.commit()

    assert updated.search_read_enabled is True
    assert updated.object_read_enabled is True
    assert updated.object_write_enabled is False
    assert updated.last_modified_by == identity_id

    reloaded = service.get(org_id)
    assert reloaded.search_read_enabled is True
    assert reloaded.object_read_enabled is True
    assert reloaded.object_write_enabled is False


def test_update_twice_upserts_the_same_row(db_session, org_id, identity_id):
    service = _service(db_session)

    service.update(org_id, True, False, False, identity_id)
    db_session.commit()
    service.update(org_id, False, True, True, identity_id)
    db_session.commit()

    settings = service.get(org_id)
    assert settings.search_read_enabled is False
    assert settings.object_read_enabled is True
    assert settings.object_write_enabled is True


def test_settings_are_isolated_per_org(db_session, org_id, identity_id):
    other_org_id = OrganizationRepository(db_session).create("Other Org", "other-org").id
    db_session.commit()
    service = _service(db_session)

    service.update(org_id, True, True, True, identity_id)
    db_session.commit()

    assert service.get(other_org_id).search_read_enabled is False
