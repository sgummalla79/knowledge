from sqlalchemy.exc import IntegrityError

from app.config import config
from app.constants import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_MCP_APPLICATION_ID,
    DEFAULT_MCP_APPLICATION_NAME,
    DEFAULT_MCP_APPLICATION_SCOPES,
)
from app.infrastructure.auth.passwords import hash_password
from app.infrastructure.auth.secrets import derive_default_mcp_client_secret, hash_secret
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.user_repository import UserRepository


def bootstrap_default_admin(session) -> None:
    """Idempotent: only creates the default admin if no user exists yet.

    Takes an explicit session rather than app.container.get_session() (which needs an active
    Flask request context via flask.g) — this runs once at app startup, before any request, and
    is also called directly by integration tests that need a seeded user without going through
    create_app(). Tolerates a duplicate-insert race (unique constraint on username) in case
    multiple workers ever start concurrently — this app now runs multiple gunicorn workers
    (docker/entrypoint.sh), each calling create_app() independently at boot.
    """
    repository = UserRepository(session)
    if repository.get() is not None:
        return
    try:
        repository.create_default(DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD))
        session.commit()
    except IntegrityError:
        session.rollback()


def bootstrap_default_mcp_application(session) -> None:
    """Idempotent: only creates the built-in MCP service-account Application if it doesn't exist
    yet (checked by its fixed id — see app/constants.py). This is what mcp_server/client.py
    authenticates as to call this app's own REST API — no dashboard registration, no env vars.
    See derive_default_mcp_client_secret for why its secret needs no separate storage or handoff
    between this process and mcp_server/server.py's separate process.
    """
    repository = ApplicationRepository(session)
    if repository.get(DEFAULT_MCP_APPLICATION_ID) is not None:
        return
    secret = derive_default_mcp_client_secret(config.secret_key)
    try:
        repository.create(
            DEFAULT_MCP_APPLICATION_NAME,
            hash_secret(secret),
            DEFAULT_MCP_APPLICATION_SCOPES,
            id=DEFAULT_MCP_APPLICATION_ID,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
