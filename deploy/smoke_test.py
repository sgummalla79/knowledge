"""End-to-end smoke check against the isolated test stack (docker-compose.test.yml, port 13199).

Drives the real HTTP surface exactly as a human would: log in via the React login page's JSON API
(api/presentation/routes/auth_ui.py) and complete the forced first-login password change — proving
the DB, migrations, and session-login machinery all work, not just that /health responds.

Deliberately stops there for now: this app owns its own identity/org model
(api/domain/entities.py's Identity/OrgMember — see docs/DATA_MODEL.md), and every content route
(documents/categories/query) requires a real session via require_org_session, but there's no
smoke-test coverage yet of signup/org-switching/content CRUD against that session — extend this to
cover that too, the same way api/tests/integration/test_ingestion_service.py and
test_retrieval_service.py cover ingest/query once an embedding provider is configured.

Run only by deploy/test-image.sh, after the isolated stack is confirmed healthy. Never run
against the prod stack.
"""
import re
import sys

import requests

BASE_URL = "http://localhost:13199"
_ADMIN_USERNAME = "admin@local"
_ADMIN_PASSWORD = "admin"
_NEW_ADMIN_PASSWORD = "smoke-test-password-1"
# /sign-in and /change-password both serve the React SPA shell (api/presentation/web/spa.py), which
# carries its CSRF token as a JS global — every JSON POST in this app sends it back via the
# X-CSRF-Token header, not a form field.
_CSRF_JS_RE = re.compile(r'window\.__CSRF_TOKEN__="([^"]+)"')


def _extract(pattern: re.Pattern, text: str, what: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(f"smoke_test: could not find {what} in response HTML")
    return match.group(1)


def main() -> None:
    session = requests.Session()

    login_page = session.get(f"{BASE_URL}/sign-in")
    login_page.raise_for_status()
    csrf = _extract(_CSRF_JS_RE, login_page.text, "login csrf token")

    login_response = session.post(
        f"{BASE_URL}/sign-in",
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

    print("smoke_test: OK — login and forced password change both worked")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"smoke_test: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
