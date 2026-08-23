from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest

from api import create_app
from api.application.app_auth_service import AppAuthService
from api.config import config
from api.constants import JWT_ALGORITHM
from api.domain.entities import Application, Category, PersonalAccessToken, ResolvedCaller, SessionSettings
from api.infrastructure.auth.jwt_tokens import encode_access_token
from api.infrastructure.auth.token_hashing import hash_token

# AppAuthService is framework-free (see its module docstring) — tested here against fake
# repository ports, no Flask/DB involved. require_permission's bearer-token wiring is tested
# separately below via a real route (categories.py) with AppAuthService mocked.


class _FakeApplications:
    def __init__(self, application):
        self._application = application

    def get(self, application_id):
        return self._application if application_id == self._application.id else None


class _FakePersonalTokens:
    def __init__(self, token, raw_token):
        self._token = token
        self._raw_token = raw_token
        self.touched = False

    def get_by_token_hash(self, token_hash):
        return self._token if token_hash == hash_token(self._raw_token) else None

    def touch_last_used(self, token_id):
        self.touched = True


class _FakePermissions:
    def __init__(self, granted=None):
        self._granted = granted if granted is not None else frozenset()

    def resolve_permissions(self, identity_id, org_id):
        return self._granted


def _application(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="CI integration",
        description=None,
        auth_method="oauth_client_credentials",
        status="active",
        service_identity_id=uuid4(),
        execute_as_identity_id=None,
        mcp_access=False,
        api_access=True,
        created_by=None,
        last_modified_by=None,
        revoked_at=None,
        revoked_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Application(**fields)


def _personal_token(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        identity_id=uuid4(),
        org_id=uuid4(),
        name="My laptop",
        token_hash="irrelevant-overwritten-by-fake",
        token_prefix="abc123",
        mcp_access=False,
        created_at=now,
        last_used_at=None,
    )
    fields.update(overrides)
    return PersonalAccessToken(**fields)


# ── Personal access token branch ────────────────────────────────────────────────────────────────


def test_authenticate_bearer_token_resolves_valid_personal_token():
    token = _personal_token()
    service = AppAuthService(
        _FakeApplications(_application()),
        _FakePersonalTokens(token, "the-raw-token"),
        _FakePermissions(frozenset({"documents:read"})),
    )

    caller = service.authenticate_bearer_token("the-raw-token")

    assert caller == ResolvedCaller(
        org_id=token.org_id,
        identity_id=token.identity_id,
        application_id=None,
        scopes=frozenset({"documents:read"}),
        auth_method="personal_access_token",
        mcp_access=False,
        api_access=True,
    )


def test_authenticate_bearer_token_touches_last_used_on_personal_token():
    token = _personal_token()
    personal_tokens = _FakePersonalTokens(token, "the-raw-token")
    service = AppAuthService(_FakeApplications(_application()), personal_tokens, _FakePermissions())

    service.authenticate_bearer_token("the-raw-token")

    assert personal_tokens.touched is True


def test_authenticate_bearer_token_rejects_unknown_personal_token():
    token = _personal_token()
    service = AppAuthService(
        _FakeApplications(_application()), _FakePersonalTokens(token, "the-raw-token"), _FakePermissions()
    )

    assert service.authenticate_bearer_token("wrong-token") is None


def test_authenticate_bearer_token_reflects_current_permissions_not_baked_in():
    # A personal token carries no authority of its own — resolve_permissions is called fresh every
    # time, so a since-changed (or since-empty) profile is reflected immediately.
    token = _personal_token()
    service = AppAuthService(
        _FakeApplications(_application()), _FakePersonalTokens(token, "the-raw-token"), _FakePermissions(frozenset())
    )

    caller = service.authenticate_bearer_token("the-raw-token")

    assert caller.scopes == frozenset()


# ── JWT branch (oauth_client_credentials) ───────────────────────────────────────────────────────


def test_authenticate_bearer_token_resolves_valid_jwt():
    application = _application(auth_method="oauth_client_credentials")
    identity_id = uuid4()
    token = encode_access_token({"sub": str(application.id), "org_id": str(application.org_id), "identity_id": str(identity_id)}, 15)
    service = AppAuthService(
        _FakeApplications(application), _FakePersonalTokens(None, "unused"), _FakePermissions(frozenset({"documents:read"}))
    )

    caller = service.authenticate_bearer_token(token)

    assert caller == ResolvedCaller(
        org_id=application.org_id,
        identity_id=identity_id,
        application_id=application.id,
        scopes=frozenset({"documents:read"}),
        auth_method="oauth_client_credentials",
        mcp_access=False,
        api_access=True,
    )


def test_authenticate_bearer_token_rejects_expired_jwt():
    application = _application(auth_method="oauth_client_credentials")
    identity_id = uuid4()
    payload = {
        "sub": str(application.id),
        "org_id": str(application.org_id),
        "identity_id": str(identity_id),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(payload, config.secret_key, algorithm=JWT_ALGORITHM)
    service = AppAuthService(_FakeApplications(application), _FakePersonalTokens(None, "unused"), _FakePermissions())

    assert service.authenticate_bearer_token(expired_token) is None


def test_authenticate_bearer_token_rejects_jwt_for_revoked_application():
    application = _application(auth_method="oauth_client_credentials", status="revoked")
    identity_id = uuid4()
    token = encode_access_token({"sub": str(application.id), "org_id": str(application.org_id), "identity_id": str(identity_id)}, 15)
    service = AppAuthService(_FakeApplications(application), _FakePersonalTokens(None, "unused"), _FakePermissions())

    assert service.authenticate_bearer_token(token) is None


# ── require_permission, exercised via a real permission-gated route (categories.py) ────────────


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_bearer_token_without_scope_is_rejected(client):
    caller = ResolvedCaller(
        org_id=uuid4(),
        identity_id=uuid4(),
        application_id=None,
        scopes=frozenset({"documents:read"}),
        auth_method="personal_access_token",
        mcp_access=False,
        api_access=True,
    )
    with patch(
        "api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=caller
    ):
        response = client.get("/categories", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 403


def test_bearer_token_with_scope_is_accepted(client):
    caller = ResolvedCaller(
        org_id=uuid4(),
        identity_id=uuid4(),
        application_id=None,
        scopes=frozenset({"categories:read"}),
        auth_method="personal_access_token",
        mcp_access=False,
        api_access=True,
    )
    with (
        patch("api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=caller),
        patch("api.presentation.routes.categories.CategoryService.list_categories", return_value=[]),
    ):
        response = client.get("/categories", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 200


def test_bearer_token_without_api_access_is_rejected(client):
    caller = ResolvedCaller(
        org_id=uuid4(),
        identity_id=uuid4(),
        application_id=uuid4(),
        scopes=frozenset({"categories:read"}),
        auth_method="oauth_client_credentials",
        mcp_access=False,
        api_access=False,
    )
    with patch("api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=caller):
        response = client.get("/categories", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 403


def test_invalid_bearer_token_returns_structured_401(client):
    with patch("api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=None):
        response = client.get("/categories", headers={"Authorization": "Bearer bogus"})

    assert response.status_code == 401


def test_no_credentials_returns_structured_401(client):
    response = client.get("/categories")

    assert response.status_code == 401


def _category(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        parent_id=None,
        name="test-category",
        slug="test-category",
        description=None,
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Category(**fields)


# ── Dual-client-type: session cookie and bearer token both reach the same gate ──────────────────
#
# The core "properly independent, client-agnostic API" design claim from this repo's Phase A
# history, proven directly against a single route (categories.py): the exact same
# permission-gated route succeeds for a browser (session cookie) and for a Postman-style API
# client (bearer token) — both resolve through require_permission's two branches into the same
# PermissionService.resolve_permissions() check. The bearer-token half is already covered above
# (test_bearer_token_with_scope_is_accepted); this is the cookie half.


def test_session_cookie_reaches_the_same_permission_gated_route(client):
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())

    with (
        patch(
            "api.presentation.routes.app_auth.PermissionService.resolve_permissions",
            return_value=frozenset({"categories:read"}),
        ),
        patch("api.presentation.routes.categories.CategoryService.list_categories", return_value=[]),
    ):
        response = client.get("/categories")

    assert response.status_code == 200


# ── CSRF: required for cookie-authenticated mutations, exempt for bearer-token ones ─────────────
#
# The security-review fix from this repo's Phase A history: require_permission's session-cookie
# branch now validates X-CSRF-Token on mutating methods (a cookie rides along automatically on any
# cross-site request — exactly what CSRF protects against); a bearer token never does, so
# token-authenticated callers are exempt.


def test_cookie_authenticated_mutation_without_csrf_is_rejected(client):
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["csrf_token"] = "the-real-token"

    with patch(
        "api.presentation.routes.app_auth.PermissionService.resolve_permissions",
        return_value=frozenset({"categories:write"}),
    ):
        response = client.post("/categories", json={"name": "test"})  # no X-CSRF-Token header

    assert response.status_code == 401


def test_cookie_authenticated_mutation_with_correct_csrf_is_accepted(client):
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
        sess["csrf_token"] = "the-real-token"

    with (
        patch(
            "api.presentation.routes.app_auth.PermissionService.resolve_permissions",
            return_value=frozenset({"categories:write"}),
        ),
        patch("api.presentation.routes.categories.CategoryService.create_category", return_value=_category()),
    ):
        response = client.post("/categories", json={"name": "test"}, headers={"X-CSRF-Token": "the-real-token"})

    assert response.status_code == 201


def test_bearer_token_mutation_needs_no_csrf(client):
    caller = ResolvedCaller(
        org_id=uuid4(),
        identity_id=uuid4(),
        application_id=None,
        scopes=frozenset({"categories:write"}),
        auth_method="personal_access_token",
        mcp_access=False,
        api_access=True,
    )
    with (
        patch("api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=caller),
        patch("api.presentation.routes.categories.CategoryService.create_category", return_value=_category()),
    ):
        # No cookie, no X-CSRF-Token — only a bearer token.
        response = client.post("/categories", json={"name": "test"}, headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 201


# ── Session inactivity timeout, end-to-end through a real route ─────────────────────────────────
#
# The org-configurable session-inactivity feature (session_guard.resolve_cookie_session,
# session_settings) — unit-tested directly in test_session_guard.py; this is the one route-level
# regression proving it's actually wired into require_permission, not just the helper itself.


def test_stale_cookie_session_is_rejected_on_a_real_permission_gated_route(client):
    with client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())

    stale_settings = SessionSettings(
        org_id=uuid4(),
        inactivity_timeout_minutes=120,
        last_modified_by=None,
        last_modified_at=datetime.now(timezone.utc),
    )
    with (
        patch(
            "api.infrastructure.repositories.identity_repository.IdentityRepository.get_last_active_at",
            return_value=datetime.now(timezone.utc) - timedelta(hours=3),
        ),
        patch(
            "api.application.session_settings_service.SessionSettingsService.get", return_value=stale_settings
        ),
    ):
        # Rejected at the staleness check, before permission resolution is even reached.
        response = client.get("/categories")

    assert response.status_code == 401
