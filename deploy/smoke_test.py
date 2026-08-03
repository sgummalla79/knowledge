"""End-to-end smoke check against the isolated test stack (docker-compose.test.yml, port 13199).

Drives the real HTTP surface exactly as a human/client would: log into the dashboard (server-
rendered, JSON-API doesn't cover app registration by design), register an OAuth2 application,
mint a token, then create a library — proving the DB, migrations, auth/scope machinery, and core
CRUD path all work, not just that /health responds.

No embedding provider is enabled by default — every provider starts disabled until an admin
configures and enables one via its dashboard page (see
app/infrastructure/embeddings/bootstrap.py) — so this deliberately stops short of document
ingestion/query, which need one configured and enabled first. Once an embedding provider is set
up, ingest/query are exercised by tests/integration/test_ingestion_service.py and
test_retrieval_service.py instead.

Run only by deploy/test-image.sh, after the isolated stack is confirmed healthy. Never run
against the prod stack.
"""
import re
import sys

import requests

BASE_URL = "http://localhost:13199"
_ADMIN_USERNAME = "admin"
_ADMIN_PASSWORD = "admin"
_NEW_ADMIN_PASSWORD = "smoke-test-password-1"
_APP_NAME = "smoke-test"
_REQUIRED_SCOPES = ["libraries:write", "libraries:read"]
_CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
_CLIENT_ID_RE = re.compile(r'id="new-credential-client-id">([^<]+)<')
_CLIENT_SECRET_RE = re.compile(r'id="new-credential-client-secret">([^<]+)<')


def _extract(pattern: re.Pattern, text: str, what: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(f"smoke_test: could not find {what} in response HTML")
    return match.group(1)


def _register_application_and_get_token() -> str:
    session = requests.Session()

    login_page = session.get(f"{BASE_URL}/login")
    login_page.raise_for_status()
    csrf = _extract(_CSRF_RE, login_page.text, "login csrf_token")

    after_login = session.post(
        f"{BASE_URL}/login",
        data={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD, "csrf_token": csrf},
    )
    after_login.raise_for_status()

    # Fresh bootstrap always forces a password change on first login (must_change_password=True).
    csrf = _extract(_CSRF_RE, after_login.text, "change-password csrf_token")
    after_change = session.post(
        f"{BASE_URL}/change-password",
        data={
            "new_password": _NEW_ADMIN_PASSWORD,
            "confirm_password": _NEW_ADMIN_PASSWORD,
            "csrf_token": csrf,
        },
    )
    after_change.raise_for_status()

    csrf = _extract(_CSRF_RE, after_change.text, "dashboard csrf_token")
    register = session.post(
        f"{BASE_URL}/dashboard/applications",
        data=[("csrf_token", csrf), ("name", _APP_NAME)] + [("scopes", scope) for scope in _REQUIRED_SCOPES],
    )
    register.raise_for_status()
    client_id = _extract(_CLIENT_ID_RE, register.text, "new client_id")
    client_secret = _extract(_CLIENT_SECRET_RE, register.text, "new client_secret")

    token_response = requests.post(
        f"{BASE_URL}/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": " ".join(_REQUIRED_SCOPES),
        },
    )
    token_response.raise_for_status()
    return token_response.json()["access_token"]


def main() -> None:
    access_token = _register_application_and_get_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    library_response = requests.post(
        f"{BASE_URL}/libraries", json={"name": "smoke-test-library"}, headers=headers
    )
    library_response.raise_for_status()
    library_id = library_response.json()["id"]

    get_response = requests.get(f"{BASE_URL}/libraries/{library_id}", headers=headers)
    get_response.raise_for_status()
    if get_response.json()["name"] != "smoke-test-library":
        raise RuntimeError("smoke_test: library round-trip returned unexpected data")

    print("smoke_test: OK — auth, scopes, and library CRUD all worked")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"smoke_test: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
