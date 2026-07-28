"""End-to-end smoke check against the isolated test stack (docker-compose.test.yml, port 13199).

Drives the real HTTP surface exactly as a human/client would: log into the dashboard (server-
rendered, JSON-API doesn't cover app registration by design), register an OAuth2 application,
mint a token, then create a library, ingest a document, and query it — proving the bundled Ollama
sidecar's embedding pipeline actually works end to end, not just that migrations applied and
/health responds.

Run only by scripts/test-image.sh, after the isolated stack is confirmed healthy. Never run
against the prod stack.
"""
import re
import sys
import time

import requests

BASE_URL = "http://localhost:13199"
_ADMIN_USERNAME = "admin"
_ADMIN_PASSWORD = "admin"
_NEW_ADMIN_PASSWORD = "smoke-test-password-1"
_APP_NAME = "smoke-test"
_REQUIRED_SCOPES = [
    "libraries:write",
    "libraries:read",
    "documents:write",
    "documents:read",
    "query:execute",
]
_JOB_POLL_TIMEOUT_SECONDS = 60
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


def _wait_for_job(headers: dict, library_id: str, job_id: str) -> None:
    deadline = time.monotonic() + _JOB_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = requests.get(f"{BASE_URL}/libraries/{library_id}/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        status = response.json()["status"]
        if status == "completed":
            return
        if status == "failed":
            raise RuntimeError(f"smoke_test: ingestion job failed: {response.json()['error']}")
        time.sleep(1)
    raise RuntimeError(f"smoke_test: ingestion job did not complete within {_JOB_POLL_TIMEOUT_SECONDS}s")


def main() -> None:
    access_token = _register_application_and_get_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    library_response = requests.post(
        f"{BASE_URL}/libraries", json={"name": "smoke-test-library"}, headers=headers
    )
    library_response.raise_for_status()
    library_id = library_response.json()["id"]

    document_content = (
        b"The knowledge-api smoke test verifies that the bundled Ollama sidecar can embed and "
        b"retrieve real content end to end."
    )
    upload_response = requests.post(
        f"{BASE_URL}/libraries/{library_id}/documents",
        files={"file": ("smoke-test.txt", document_content, "text/plain")},
        headers=headers,
    )
    upload_response.raise_for_status()
    job_id = upload_response.json()["job_id"]

    _wait_for_job(headers, library_id, job_id)

    query_response = requests.post(
        f"{BASE_URL}/libraries/{library_id}/query",
        json={"query": "What does the smoke test verify?", "top_k": 1},
        headers=headers,
    )
    query_response.raise_for_status()
    chunks = query_response.json()["chunks"]
    if not chunks:
        raise RuntimeError("smoke_test: query returned zero chunks")

    print(f"smoke_test: OK — ingested and queried successfully ({len(chunks)} chunk(s) returned)")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"smoke_test: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
