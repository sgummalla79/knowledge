from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api import create_app
from api.domain.entities import PersonalAccessToken
from api.domain.errors import NotFoundError

# HTTP-layer wiring only — PersonalAccessTokenService is mocked; real create/delete/ownership
# behavior is exercised by api/tests/integration. Gated by require_org_session (any authenticated
# member of the active org), not require_permission — no permission fixture needed here.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["identity_id"] = str(uuid4())
        sess["active_org_id"] = str(uuid4())
    return test_client


def _token(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        identity_id=uuid4(),
        org_id=uuid4(),
        name="My laptop",
        token_hash="irrelevant",
        token_prefix="abc123",
        mcp_access=False,
        created_at=now,
        last_used_at=None,
    )
    fields.update(overrides)
    return PersonalAccessToken(**fields)


def test_requires_authentication(client):
    unauthenticated = client.application.test_client()
    response = unauthenticated.get("/personal-access-tokens")

    assert response.status_code == 401


def test_create_returns_201_with_one_time_token(client):
    token = _token(name="CI script")
    with patch(
        "api.presentation.routes.personal_access_tokens.PersonalAccessTokenService.create",
        return_value=(token, "raw-token-value"),
    ):
        response = client.post("/personal-access-tokens", json={"name": "CI script"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["token"] == "raw-token-value"
    assert body["name"] == "CI script"
    assert "token_hash" not in body


def test_create_missing_name_returns_structured_400(client):
    response = client.post("/personal-access-tokens", json={})

    assert response.status_code == 400
    assert response.get_json()["error"]["field"] == "name"


def test_list_returns_tokens_without_secret(client):
    token = _token()
    with patch(
        "api.presentation.routes.personal_access_tokens.PersonalAccessTokenService.list_for_identity",
        return_value=[token],
    ):
        response = client.get("/personal-access-tokens")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body) == 1
    assert body[0]["token_prefix"] == "abc123"
    assert "token" not in body[0]


def test_delete_returns_204(client):
    with patch("api.presentation.routes.personal_access_tokens.PersonalAccessTokenService.delete", return_value=None):
        response = client.delete(f"/personal-access-tokens/{uuid4()}")

    assert response.status_code == 204


def test_delete_not_found_or_not_owned_returns_structured_404(client):
    with patch(
        "api.presentation.routes.personal_access_tokens.PersonalAccessTokenService.delete",
        side_effect=NotFoundError("personal_access_token_not_found", "API key not found."),
    ):
        response = client.delete(f"/personal-access-tokens/{uuid4()}")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "personal_access_token_not_found"
