"""Real-server concurrency regression tests -- see this directory's conftest.py for why a genuine
subprocess (not app.test_client()) is needed to reproduce this bug class at all.

Reproduces two real production incidents (2026-08-24) directly:
1. A single browser page load fires several concurrent requests for the same signed-in identity
   (documents/shelves/categories/dashboard stats/etc. all at once) -- these piled up behind a lock
   on the identities row (touch_last_active, api/presentation/web/session_guard.py) and started
   failing with 500 db_lock_timeout once enough queued up.
2. Even two back-to-back requests held that same lock for a whole request's lifetime instead of
   just the write itself, serializing unrelated work unnecessarily.

Both are fixed now (session_guard.py commits the touch immediately) -- these tests exist so a
regression is caught in CI, not rediscovered by a user hitting a live 500.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import requests


def _sign_up_fresh_org(live_server_url: str) -> requests.Session:
    session = requests.Session()
    csrf = session.get(f"{live_server_url}/csrf-token", timeout=10).json()["csrf_token"]
    suffix = uuid4().hex[:10]
    response = session.post(
        f"{live_server_url}/sign-up",
        json={
            "username": f"concurrency-check-{suffix}@example.com",
            "password": "TestPassword123!",
            "name": "Concurrency Check",
            "org_name": f"concurrency-check-{suffix}",
            "email": f"concurrency-check-{suffix}@example.com",
        },
        headers={"X-CSRF-Token": csrf},
        timeout=10,
    )
    response.raise_for_status()
    return session


def test_concurrent_requests_from_one_identity_do_not_lock_contend(live_server_url):
    session = _sign_up_fresh_org(live_server_url)

    # The exact endpoint mix a single real page load fires at once -- see the production log
    # excerpt this test is modeled on (documents/shelves/categories/stats/dashboard/ingestion-jobs
    # all in parallel, each independently touching the identities row via touch_last_active).
    paths = ["/documents", "/shelves", "/categories", "/stats/dashboard", "/ingestion-jobs"] * 4

    def fetch(path):
        return session.get(f"{live_server_url}{path}", timeout=15)

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(paths)) as pool:
        results = list(pool.map(fetch, paths))
    elapsed = time.monotonic() - start

    statuses = [r.status_code for r in results]
    assert all(status == 200 for status in statuses), statuses
    # The original incident: these piled up behind a held lock and started failing with
    # db_lock_timeout (a 10s server-side timeout) once enough queued up. A generous bound well
    # under that confirms the lock isn't being held across each request's full lifetime.
    assert elapsed < 5.0, f"20 concurrent requests from one identity took {elapsed:.2f}s"


def test_touch_last_active_lock_is_released_before_request_ends(live_server_url):
    """Narrower, cheaper regression test for the exact mechanism fixed in session_guard.py:
    two sequential single requests from the same identity should each be fast on their own --
    if the row lock were still held for a request's whole lifetime, the second request would show
    it as added latency even without any concurrency involved."""
    session = _sign_up_fresh_org(live_server_url)

    durations = []
    for _ in range(3):
        start = time.monotonic()
        response = session.get(f"{live_server_url}/session", timeout=15)
        durations.append(time.monotonic() - start)
        assert response.status_code == 200

    assert all(d < 1.0 for d in durations), durations
