import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app(testing=True, bootstrap_admin=False)
    return app.test_client()


def test_health_route_echoes_generated_request_id_header(client):
    response = client.get("/health")

    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


def test_health_route_honors_incoming_request_id_header(client):
    response = client.get("/health", headers={"X-Request-ID": "client-supplied-id"})

    assert response.headers["X-Request-ID"] == "client-supplied-id"


def test_two_requests_get_different_generated_request_ids(client):
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]

    assert first != second
