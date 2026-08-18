"""End-to-end smoke check against the isolated test stack (docker-compose.test.yml, port 13199).

Drives the real HTTP surface exactly as a human would: log in via the React login page's JSON API
(app/presentation/routes/auth_ui.py) and complete the forced first-login password change — proving
the DB, migrations, and session-login machinery all work, not just that /health responds.

Deliberately stops there for now: OAuth2/application registration was removed (auth is being
redesigned as a separate standalone identity service, not yet built — see docs/DATA_MODEL.md), so
every content route (documents/categories/query) is currently unauthenticated and org-scoped only
via container.get_default_org_id() — there's no per-user identity yet worth smoke-testing against a
real login session. Once the standalone auth service lands, extend this to cover content CRUD too,
the same way tests/integration/test_ingestion_service.py and test_retrieval_service.py cover
ingest/query once an embedding provider is configured.

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
# /login and /change-password both serve the React SPA shell (app/presentation/web/spa.py), which
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

    print("smoke_test: OK — login and forced password change both worked")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"smoke_test: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
