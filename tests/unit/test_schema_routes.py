from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import create_app
from app.domain.entities import User

# HTTP-layer only — no service is exercised beyond auth gating, since schema.html is static
# content with no dynamic data.


@pytest.fixture()
def client():
    app = create_app(testing=True)
    return app.test_client()


def _logged_in(client):
    with client.session_transaction() as sess:
        sess["user_id"] = str(uuid4())
        sess["csrf_token"] = "test-csrf-token"
    return "test-csrf-token"


def _user(**overrides):
    fields = dict(
        id=uuid4(),
        username="admin",
        password_hash="hashed",
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return User(**fields)


def test_schema_requires_login(client):
    response = client.get("/dashboard/schema")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")


def test_schema_renders_for_logged_in_user(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user()):
        response = client.get("/dashboard/schema")
    assert response.status_code == 200
    assert b"Data Model" in response.data
    assert b"authorization_codes" in response.data
    assert b"erDiagram" in response.data


def test_schema_redirects_to_change_password_when_required(client):
    _logged_in(client)
    with patch(
        "app.presentation.routes.auth_ui.UserRepository.get", return_value=_user(must_change_password=True)
    ):
        response = client.get("/dashboard/schema")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/change-password")


def test_sidebar_links_to_data_model(client):
    _logged_in(client)
    with patch("app.presentation.routes.auth_ui.UserRepository.get", return_value=_user()):
        response = client.get("/dashboard/schema")
    assert b'href="/dashboard/schema"' in response.data
