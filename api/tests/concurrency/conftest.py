import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests
from alembic import command
from alembic.config import Config as AlembicConfig
from testcontainers.postgres import PostgresContainer

# Duplicated from api/tests/integration/conftest.py rather than imported — same precedent
# api/mcp_server/tests/integration/conftest.py already established (api/tests/ has no __init__.py,
# so there's no clean package path to import its fixtures from).

API_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = API_ROOT.parent


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        url = postgres.get_connection_url()
        alembic_cfg = AlembicConfig(str(API_ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_cfg, "head")
        yield url


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(base_url: str, proc: subprocess.Popen, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"live server process exited early with code {proc.returncode}")
        try:
            if requests.get(f"{base_url}/health", timeout=1).status_code == 200:
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.2)
    raise TimeoutError(f"live server never became healthy within {timeout_s}s")


@pytest.fixture(scope="session")
def live_server_url(postgres_url):
    """Launches the real ASGI app (api.asgi:app -- the same uvicorn worker gunicorn runs in
    production) as a genuine subprocess bound to a free port, with DATABASE_URL pointed at the
    ephemeral Postgres above. This is what makes the tests in this directory able to prove real
    concurrent-request behavior -- app.test_client() (used everywhere else in this suite) is
    single-threaded and in-process, so it structurally cannot reproduce a lock-contention bug like
    the one this directory exists to catch.

    A real subprocess, with DATABASE_URL set before any api.* import happens inside it, sidesteps
    the module-level engine/SessionLocal singleton entirely (api/infrastructure/orm/base.py reads
    config.database_url once at import time) -- monkeypatching SessionLocal per-module the way
    api/tests/integration/test_document_service.py's session_factory fixture does only works
    because that test targets one specific already-imported module; a live server touches dozens
    of modules, each with its own independently-bound `from api.infrastructure.orm import
    SessionLocal`. This is exactly how api/deploy/smoke_test.py already tests the real thing,
    just launched here directly instead of via docker-compose.test.yml."""
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": postgres_url, "SECRET_KEY": "test-secret-key"}
    proc = subprocess.Popen(
        ["api/.venv/bin/python", "-m", "uvicorn", "api.asgi:app", "--port", str(port), "--log-level", "warning"],
        env=env,
        cwd=str(REPO_ROOT),
    )
    # No "/knowledge" prefix here -- that's added by Traefik's path-based routing in production
    # (api/deploy/k3s/04-middleware.yaml strips it before forwarding); the Flask app's own routes
    # are unprefixed, same as every local dev-preview run against this app directly.
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base_url, proc)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
