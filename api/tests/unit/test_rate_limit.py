from unittest.mock import patch

import pytest

from api import create_app
from api.constants import LOGIN_RATE_LIMIT
from api.domain.errors import AuthenticationError


@pytest.fixture()
def client():
    # testing=False so the limiter is actually enabled; a tiny override limit keeps the test
    # fast and deterministic instead of hammering the real "200 per minute" default.
    # bootstrap_admin=False: this test has no real database behind it (see the route comment
    # below), so the DB-seeding step must be skipped explicitly.
    app = create_app(
        testing=False,
        rate_limit_default="2 per minute",
        bootstrap_admin=False
    )
    return app.test_client()


def test_exceeding_rate_limit_returns_structured_429(client):
    # Uses a route that doesn't need a real DB connection, so the only thing under test is
    # the rate limiter itself, not downstream business logic.
    for _ in range(2):
        response = client.get("/embedding-options")
        assert response.status_code != 429

    response = client.get("/embedding-options")
    assert response.status_code == 429
    body = response.get_json()
    assert body["error"]["code"] == "rate_limited"


@pytest.fixture()
def login_client():
    # POST /sign-in carries its own dedicated LOGIN_RATE_LIMIT (see api/constants.py and this
    # repo's Phase A security review) rather than inheriting rate_limit_default — no override
    # needed here, the route's own decorator already applies a tight limit.
    app = create_app(testing=False, bootstrap_admin=False)
    return app.test_client()


def test_login_rate_limit_returns_structured_429_before_the_limit(login_client):
    attempts = int(LOGIN_RATE_LIMIT.split(" ")[0])
    with patch(
        "api.presentation.routes.auth_ui.AuthService.login",
        side_effect=AuthenticationError("Invalid username or password."),
    ):
        for _ in range(attempts):
            response = login_client.post("/sign-in", json={"username": "attacker@example.com", "password": "wrong"})
            assert response.status_code != 429

        response = login_client.post("/sign-in", json={"username": "attacker@example.com", "password": "wrong"})

    assert response.status_code == 429
    assert response.get_json()["error"]["code"] == "rate_limited"
