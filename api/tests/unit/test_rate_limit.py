import pytest

from api import create_app


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
