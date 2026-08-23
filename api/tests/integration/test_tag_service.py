import pytest

from api.application.tag_service import TagService
from api.infrastructure.auth.bootstrap import bootstrap_default_organization
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.tag_repository import TagRepository


@pytest.fixture()
def org_id(db_session):
    return bootstrap_default_organization(db_session).id


def _service(db_session) -> TagService:
    return TagService(TagRepository(db_session))


def test_create_tag_persists_and_is_listed(db_session, org_id):
    service = _service(db_session)

    created = service.create_tag(org_id, "billing")
    db_session.commit()

    assert created.name == "billing"
    assert [tag.id for tag in service.list_tags(org_id)] == [created.id]


def test_create_tag_reuses_existing_tag_case_insensitively(db_session, org_id):
    service = _service(db_session)

    first = service.create_tag(org_id, "billing")
    db_session.commit()
    second = service.create_tag(org_id, "Billing")
    db_session.commit()

    # No new row created — the case-variant name resolves to the exact same tag rather than a
    # second, near-duplicate one. This is the case-insensitive get-or-create moved server-side so
    # every caller (not just webui's own pre-check) gets it — see TagService.create_tag.
    assert second.id == first.id
    assert len(service.list_tags(org_id)) == 1


def test_create_tag_reuses_exact_name_too(db_session, org_id):
    service = _service(db_session)

    first = service.create_tag(org_id, "billing")
    db_session.commit()
    second = service.create_tag(org_id, "billing")
    db_session.commit()

    assert second.id == first.id
    assert len(service.list_tags(org_id)) == 1


def test_create_tag_is_isolated_per_org(db_session, org_id):
    other_org_id = OrganizationRepository(db_session).create("Other Org", "other-org").id
    db_session.commit()
    service = _service(db_session)

    service.create_tag(org_id, "billing")
    db_session.commit()
    other = service.create_tag(other_org_id, "billing")
    db_session.commit()

    assert [tag.id for tag in service.list_tags(other_org_id)] == [other.id]
