from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from api import create_app
from api.domain.entities import Identity, Organization
from api.presentation.web.asgi_bridge import build_asgi_app

# The one empirically-unverified assumption the MCP-merge redesign rests on: that wrapping Flask
# via a2wsgi.WSGIMiddleware and mounting it under Starlette preserves session cookies/CSRF exactly
# as gunicorn's own gthread workers already do. WSGI-in-ASGI operates purely at the transport
# layer and never touches Flask's internal request handling, so this was expected to just work —
# this test is the actual proof, not an assumption.
#
# HTTP-layer only, same as test_login_routes.py: AuthService is mocked, no real DB involved (the
# thing under test is the ASGI/WSGI bridge itself, not login business logic).


def _identity(**overrides):
    fields = dict(
        id=uuid4(),
        username="admin@local",
        email=None,
        name="Admin",
        password_hash="hashed",
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
        last_active_at=None,
    )
    fields.update(overrides)
    return Identity(**fields)


def _org(**overrides):
    now = datetime.now(timezone.utc)
    fields = dict(
        id=uuid4(),
        name="acme-labs",
        slug="acme-labs",
        description=None,
        plan="free",
        created_by=None,
        last_modified_by=None,
        created_at=now,
        last_modified_at=now,
    )
    fields.update(overrides)
    return Organization(**fields)


@pytest.fixture()
def client():
    flask_app = create_app(testing=True)
    asgi_app = build_asgi_app(flask_app)
    return TestClient(asgi_app)


def test_health_route_reachable_through_bridge(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_session_cookie_and_csrf_survive_the_bridge(client):
    csrf_response = client.get("/csrf-token")
    assert csrf_response.status_code == 200
    csrf = csrf_response.json()["csrf_token"]
    assert csrf

    org = _org()
    with (
        patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity()),
        patch("api.presentation.routes.auth_ui.AuthService.list_orgs_for_identity", return_value=[org.id]),
        patch("api.presentation.routes.auth_ui.OrganizationRepository.get", return_value=org),
    ):
        login_response = client.post(
            "/sign-in", json={"username": "admin@local", "password": "admin"}, headers={"X-CSRF-Token": csrf}
        )
    assert login_response.status_code == 200
    assert login_response.json()["redirect"] == f"/{org.slug}"

    # No cookies passed explicitly — TestClient persists them across requests the same way a real
    # browser or gunicorn-served session would, proving the session Flask set on the login response
    # above survived being routed back out through the ASGI/WSGI bridge and back in on this request.
    with (
        patch("api.presentation.routes.auth_ui.IdentityRepository.get_by_id", return_value=_identity()),
        patch("api.presentation.routes.auth_ui.OrganizationRepository.get", return_value=org),
    ):
        session_response = client.get("/session")
    assert session_response.status_code == 200
    assert session_response.json()["org_slug"] == org.slug


async def _post_without_content_length(asgi_app, body: bytes):
    """Drives an ASGI app directly with a Content-Length-less request (TestClient/httpx always
    computes and sends one for a buffered body, so it can't reproduce this) -- matches what
    a2wsgi.WSGIMiddleware actually receives when the real header is missing on the way in, e.g. a
    large upload Traefik forwards to this backend as chunked transfer-encoding rather than a fixed
    length."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/echo",
        "raw_path": b"/echo",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
    }
    sent = {"done": False}

    async def receive():
        if not sent["done"]:
            sent["done"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    messages = []

    async def send(message):
        messages.append(message)

    await asgi_app(scope, receive, send)
    return b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")


def _echo_wsgi_app(environ, start_response):
    """Minimal WSGI app for the regression test below -- just reports how much of the real body it
    was actually able to read, independent of any Flask/pydantic/business logic that could mask the
    bug (see the test docstring for why /sign-in's own mocking turned out not to)."""
    from werkzeug.wsgi import get_input_stream

    data = get_input_stream(environ, max_content_length=1024).read()
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [data]


def test_body_survives_the_bridge_without_a_content_length_header():
    """The actual regression case fixed by asgi_bridge.py's _mark_input_terminated: a POST whose
    Content-Length header is missing must still have its real body delivered to the WSGI app, not
    silently replaced with an empty stream. Without the flag it sets, Werkzeug's get_input_stream
    (used by both raw WSGI apps and, underneath, every Flask request) falls back to its DoS-safety
    default of treating a Content-Length-less request as bodyless -- even though a2wsgi's ASGI-
    backed Body always has the real bytes queued up and ready to read (see _mark_input_terminated's
    own docstring for the full mechanism). Talks to a's own tiny WSGI app rather than a real Flask
    route: an earlier version of this test used /sign-in, but AuthService being mocked there meant
    the route never actually depended on the body content, so it passed even with the bug present --
    a false positive this version avoids entirely."""
    import asyncio

    from a2wsgi import WSGIMiddleware

    from api.presentation.web.asgi_bridge import _mark_input_terminated

    body = b"the real uploaded bytes, all of them"

    broken_app = WSGIMiddleware(_echo_wsgi_app)
    received = asyncio.run(_post_without_content_length(broken_app, body))
    assert received == b"", "expected the pre-fix a2wsgi wiring to lose the body; test needs updating if it didn't"

    fixed_app = WSGIMiddleware(_mark_input_terminated(_echo_wsgi_app))
    received = asyncio.run(_post_without_content_length(fixed_app, body))
    assert received == body


def test_wrong_csrf_still_rejected_through_bridge(client):
    csrf_response = client.get("/csrf-token")
    assert csrf_response.json()["csrf_token"]

    with patch("api.presentation.routes.auth_ui.AuthService.login", return_value=_identity()):
        response = client.post(
            "/sign-in", json={"username": "admin@local", "password": "admin"}, headers={"X-CSRF-Token": "wrong-token"}
        )
    assert response.status_code == 401
