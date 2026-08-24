"""Regression test for a real production incident (2026-08-24): an identity whose last_active_at
was already older than its org's inactivity_timeout_minutes could never log in again -- every
fresh login re-established a session against that same stale timestamp, so the very next request
failed the identical inactivity check again, before ever getting a chance to refresh it.

api/tests/unit/test_login_routes.py::test_sign_in_success_refreshes_last_active_at already proves
_establish_session *calls* touch_last_active (mocked). This test drives the real HTTP routes
end-to-end against a real DB -- POST /sign-in then GET /session, exactly what a browser does --
so it actually regresses if the fix is ever removed from auth_ui.py, not just if the underlying
mechanism breaks.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import create_app
from api.application.profile_service import ProfileService
from api.infrastructure.auth.passwords import hash_password
from api.infrastructure.orm import Identity as IdentityModel
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository
from api.infrastructure.repositories.organization_repository import OrganizationRepository
from api.infrastructure.repositories.profile_repository import ProfileRepository
from api.infrastructure.repositories.session_settings_repository import SessionSettingsRepository


def test_login_recovers_an_identity_whose_session_had_already_aged_past_the_timeout(
    db_session, postgres_url, monkeypatch
):
    org = OrganizationRepository(db_session).create("acme-labs", "acme-labs", created_by=None, last_modified_by=None)
    identity = IdentityRepository(db_session).create(
        "ada@acme.com", hash_password("correct-password"), name="Ada", must_change_password=False
    )
    # _establish_session (api/presentation/routes/auth_ui.py) only populates active_org_id when
    # the identity actually has a membership -- without one, GET /session would 401 for an
    # unrelated reason (no active_org_id in the session at all) and this test wouldn't actually be
    # exercising the inactivity-timeout path it exists to cover.
    admin_profile = ProfileService(ProfileRepository(db_session)).create_admin_profile(org.id, identity.id)
    OrgMemberRepository(db_session).create(org.id, identity.id, admin_profile.id)
    SessionSettingsRepository(db_session).upsert(org.id, inactivity_timeout_minutes=1, modified_by=None)

    # Simulates a session that's genuinely long dead -- far older than the 1-minute timeout above.
    model = db_session.get(IdentityModel, identity.id)
    model.last_active_at = datetime.now(timezone.utc) - timedelta(hours=12)
    db_session.commit()

    # get_session() (api/container.py) resolves SessionLocal at call time via flask.g -- point it
    # at the real testcontainers DB for the duration of this test, same technique
    # api/tests/integration/test_document_service.py's session_factory fixture already uses for a
    # different module's SessionLocal reference.
    engine = create_engine(postgres_url)
    monkeypatch.setattr("api.container.SessionLocal", sessionmaker(bind=engine))

    app = create_app(testing=True, bootstrap_admin=False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf-token"

    sign_in = client.post(
        "/sign-in",
        json={"username": "ada@acme.com", "password": "correct-password"},
        headers={"X-CSRF-Token": "test-csrf-token"},
    )
    assert sign_in.status_code == 200, sign_in.get_json()

    # The exact request that used to fail: the very next GET /session after a fresh sign-in on an
    # identity whose prior session had already aged past the org's inactivity timeout.
    session_check = client.get("/session")
    assert session_check.status_code == 200, session_check.get_json()
    assert session_check.get_json()["username"] == "ada@acme.com"

    engine.dispose()
