import pytest

from api.application.session_settings_service import SessionSettingsService
from api.constants import SESSION_TIMEOUT_DEFAULT_MINUTES
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.session_settings_repository import SessionSettingsRepository


@pytest.fixture()
def org_id(db_session):
    return bootstrap_default_organization(db_session).id


@pytest.fixture()
def identity_id(db_session):
    # last_modified_by is a real FK to identities.id, unlike most other test callers that pass a
    # bare uuid4() for a caller not actually checked against the DB.
    return IdentityRepository(db_session).create("session-settings-tester@acme.com", "hashed", name="Tester").id


def _service(db_session) -> SessionSettingsService:
    return SessionSettingsService(SessionSettingsRepository(db_session))


def test_get_defaults_to_default_timeout_when_no_row_exists(db_session, org_id):
    settings = _service(db_session).get(org_id)

    assert settings.org_id == org_id
    assert settings.inactivity_timeout_minutes == SESSION_TIMEOUT_DEFAULT_MINUTES


def test_update_persists_and_get_reflects_it(db_session, org_id, identity_id):
    service = _service(db_session)

    updated = service.update(org_id, 30, identity_id)
    db_session.commit()

    assert updated.inactivity_timeout_minutes == 30
    assert updated.last_modified_by == identity_id

    reloaded = service.get(org_id)
    assert reloaded.inactivity_timeout_minutes == 30


def test_update_twice_upserts_the_same_row(db_session, org_id, identity_id):
    service = _service(db_session)

    service.update(org_id, 30, identity_id)
    db_session.commit()
    service.update(org_id, 1440, identity_id)
    db_session.commit()

    assert service.get(org_id).inactivity_timeout_minutes == 1440


def test_settings_are_isolated_per_org(db_session, org_id, identity_id):
    other_org_id = OrganizationRepository(db_session).create("Other Org", "other-org").id
    db_session.commit()
    service = _service(db_session)

    service.update(org_id, 15, identity_id)
    db_session.commit()

    assert service.get(other_org_id).inactivity_timeout_minutes == SESSION_TIMEOUT_DEFAULT_MINUTES
