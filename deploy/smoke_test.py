"""End-to-end smoke check against the isolated test stack (docker-compose.test.yml, port 13199).

Drives the real HTTP surface exactly as a human/client would: log in via the React login page's
JSON API (app/presentation/routes/auth_ui.py), register an OAuth2 application via the still-
server-rendered dashboard (JSON-API doesn't cover app registration by design), mint a token, then
create a library — proving the DB, migrations, auth/scope machinery, and core CRUD path all work,
not just that /health responds.

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
# /login and /change-password serve the React SPA shell (app/presentation/web/spa.py), which
# carries its CSRF token as a JS global rather than a Jinja hidden field — /dashboard and its
# Applications form are still server-rendered Jinja, using the older hidden-field convention.
# Both are the same session-stored token value, just presented two different ways.
_CSRF_JS_RE = re.compile(r'window\.__CSRF_TOKEN__="([^"]+)"')
_CSRF_FORM_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
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
    csrf = _extract(_CSRF_JS_RE, login_page.text, "login csrf token")

    login_response = session.post(
        f"{BASE_URL}/login",
        json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    login_response.raise_for_status()

    # Fresh bootstrap always forces a password change on first login (must_change_password=True).
    # Same session, same CSRF token throughout — it's never rotated mid-session.
    change_response = session.post(
        f"{BASE_URL}/change-password",
        json={"new_password": _NEW_ADMIN_PASSWORD, "confirm_password": _NEW_ADMIN_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    change_response.raise_for_status()

    dashboard_page = session.get(f"{BASE_URL}/dashboard")
    dashboard_page.raise_for_status()
    csrf = _extract(_CSRF_FORM_RE, dashboard_page.text, "dashboard csrf_token")
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
