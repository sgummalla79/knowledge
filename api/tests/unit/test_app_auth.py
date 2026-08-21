from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest

from api import create_app
from api.application.app_auth_service import AppAuthService
from api.config import config
from api.constants import JWT_ALGORITHM
from api.domain.entities import Application, ApplicationApiKey, ResolvedCaller
from api.infrastructure.auth.jwt_tokens import encode_access_token
from api.infrastructure.auth.token_hashing import hash_token

# AppAuthService is framework-free (see its module docstring) — tested here against fake
# repository ports, no Flask/DB involved. require_permission's bearer-token wiring is tested
# separately below via a real route (categories.py) with AppAuthService mocked.


class _FakeApplications:
    def __init__(self, application, scopes):
        self._application = application
        self._scopes = scopes

    def get(self, application_id):
        return self._application if application_id == self._application.id else None

    def list_scopes(self, application_id):
        return self._scopes


class _FakeApiKeys:
    def __init__(self, api_key, raw_key):
        self._api_key = api_key
        self._raw_key = raw_key
        self.touched = False

    def get_by_key_hash(self, key_hash):
        return self._api_key if key_hash == hash_token(self._raw_key) else None

    def touch_last_used(self, application_id):
        self.touched = True


class _FakePermissions:
    """Only ever consulted by the JWT branch — a pure API-key-shaped token never reaches it, so
    tests that don't care about it pass one that errors loudly if it's ever unexpectedly called."""

    def __init__(self, granted=None):
        self._granted = granted

    def resolve_permissions(self, identity_id, org_id):
        if self._granted is None:
            raise AssertionError("resolve_permissions should not be called for this test")
        return self._granted


def _application(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        org_id=uuid4(),
        name="CI integration",
        description=None,
        auth_method="api_key",
        status="active",
        service_identity_id=uuid4(),
        execute_as_identity_id=None,
        mcp_access=False,
        created_by=None,
        last_modified_by=None,
        revoked_at=None,
        revoked_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Application(**fields)


def _api_key(application_id, **overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        application_id=application_id,
        key_hash="irrelevant-overwritten-by-fake",
        key_prefix="abc123",
        created_at=now,
        last_rotated_at=now,
        last_used_at=None,
        revoked_at=None,
    )
    fields.update(overrides)
    return ApplicationApiKey(**fields)


def test_authenticate_bearer_token_resolves_valid_key():
    application = _application()
    api_key = _api_key(application.id)
    service = AppAuthService(
        _FakeApplications(application, ["documents:read"]), _FakeApiKeys(api_key, "the-raw-key"), _FakePermissions()
    )

    caller = service.authenticate_bearer_token("the-raw-key")

    assert caller == ResolvedCaller(
        org_id=application.org_id,
        identity_id=application.service_identity_id,
        application_id=application.id,
        scopes=frozenset({"documents:read"}),
        auth_method="api_key",
        mcp_access=False,
    )


def test_authenticate_bearer_token_rejects_unknown_key():
    application = _application()
    api_key = _api_key(application.id)
    service = AppAuthService(
        _FakeApplications(application, ["documents:read"]), _FakeApiKeys(api_key, "the-raw-key"), _FakePermissions()
    )

    assert service.authenticate_bearer_token("wrong-key") is None


def test_authenticate_bearer_token_rejects_revoked_key():
    application = _application()
    api_key = _api_key(application.id, revoked_at=datetime.now(timezone.utc))
    service = AppAuthService(
        _FakeApplications(application, ["documents:read"]), _FakeApiKeys(api_key, "the-raw-key"), _FakePermissions()
    )

    assert service.authenticate_bearer_token("the-raw-key") is None


def test_authenticate_bearer_token_rejects_revoked_application():
    application = _application(status="revoked")
    api_key = _api_key(application.id)
    service = AppAuthService(
        _FakeApplications(application, ["documents:read"]), _FakeApiKeys(api_key, "the-raw-key"), _FakePermissions()
    )

    assert service.authenticate_bearer_token("the-raw-key") is None


# ── JWT branch (oauth_client_credentials) ───────────────────────────────────────────────────────


def test_authenticate_bearer_token_resolves_valid_jwt():
    application = _application(auth_method="oauth_client_credentials")
    identity_id = uuid4()
    token = encode_access_token({"sub": str(application.id), "org_id": str(application.org_id), "identity_id": str(identity_id)}, 15)
    service = AppAuthService(
        _FakeApplications(application, []), _FakeApiKeys(None, "unused"), _FakePermissions(frozenset({"documents:read"}))
    )

    caller = service.authenticate_bearer_token(token)

    assert caller == ResolvedCaller(
        org_id=application.org_id,
        identity_id=identity_id,
        application_id=application.id,
        scopes=frozenset({"documents:read"}),
        auth_method="oauth_client_credentials",
        mcp_access=False,
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
    service = AppAuthService(_FakeApplications(application, []), _FakeApiKeys(None, "unused"), _FakePermissions())

    assert service.authenticate_bearer_token(expired_token) is None


def test_authenticate_bearer_token_rejects_jwt_for_revoked_application():
    application = _application(auth_method="oauth_client_credentials", status="revoked")
    identity_id = uuid4()
    token = encode_access_token({"sub": str(application.id), "org_id": str(application.org_id), "identity_id": str(identity_id)}, 15)
    service = AppAuthService(_FakeApplications(application, []), _FakeApiKeys(None, "unused"), _FakePermissions())

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
        application_id=uuid4(),
        scopes=frozenset({"documents:read"}),
        auth_method="api_key",
        mcp_access=False,
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
        application_id=uuid4(),
        scopes=frozenset({"categories:read"}),
        auth_method="api_key",
        mcp_access=False,
    )
    with (
        patch("api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=caller),
        patch("api.presentation.routes.categories.CategoryService.list_categories", return_value=[]),
    ):
        response = client.get("/categories", headers={"Authorization": "Bearer whatever"})

    assert response.status_code == 200


def test_invalid_bearer_token_returns_structured_401(client):
    with patch("api.presentation.routes.app_auth.AppAuthService.authenticate_bearer_token", return_value=None):
        response = client.get("/categories", headers={"Authorization": "Bearer bogus"})

    assert response.status_code == 401


def test_no_credentials_returns_structured_401(client):
    response = client.get("/categories")

    assert response.status_code == 401
