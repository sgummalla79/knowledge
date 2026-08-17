from sqlalchemy.exc import IntegrityError

from app.config import config
from app.domain.errors import ConflictError
from app.constants import (
    DEFAULT_ADMIN_NAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_DASHBOARD_APPLICATION_ID,
    DEFAULT_DASHBOARD_APPLICATION_NAME,
    DEFAULT_DASHBOARD_APPLICATION_SCOPES,
    DEFAULT_MCP_APPLICATION_ID,
    DEFAULT_MCP_APPLICATION_NAME,
    DEFAULT_MCP_APPLICATION_SCOPES,
    DEFAULT_ORGANIZATION_NAME,
    DEFAULT_ORGANIZATION_SLUG,
)
from app.infrastructure.auth.passwords import hash_password
from app.infrastructure.auth.secrets import (
    derive_default_dashboard_client_secret,
    derive_default_mcp_client_secret,
    hash_secret,
)
from app.infrastructure.repositories.application_repository import ApplicationRepository
from app.infrastructure.repositories.organization_repository import OrganizationRepository
from app.infrastructure.repositories.user_repository import UserRepository


def bootstrap_default_organization(session):
    """Idempotent: returns the default org, creating it first if this is a fresh database.
    Looked up by slug (not "any org exists") since a later phase may let orgs be created through
    the API — this only ever needs to find/create the one specific bootstrap org. Public (not just
    an internal helper for bootstrap_default_admin below) since several repositories/tests need to
    ensure the default org exists independently of bootstrapping an admin user."""
    repository = OrganizationRepository(session)
    organization = repository.get_by_slug(DEFAULT_ORGANIZATION_SLUG)
    if organization is not None:
        return organization
    try:
        organization = repository.create(DEFAULT_ORGANIZATION_NAME, DEFAULT_ORGANIZATION_SLUG)
        session.commit()
        return organization
    except ConflictError:
        session.rollback()
        return repository.get_by_slug(DEFAULT_ORGANIZATION_SLUG)


def bootstrap_default_admin(session) -> None:
    """Idempotent: only creates the default admin if no user exists yet.

    Takes an explicit session rather than app.container.get_session() (which needs an active
    Flask request context via flask.g) — this runs once at app startup, before any request, and
    is also called directly by integration tests that need a seeded user without going through
    create_app(). Tolerates a duplicate-insert race (unique constraint on username) in case
    multiple workers ever start concurrently — this app now runs multiple gunicorn workers
    (deploy/entrypoint.sh), each calling create_app() independently at boot.
    """
    repository = UserRepository(session)
    if repository.get() is not None:
        return
    organization = bootstrap_default_organization(session)
    try:
        repository.create_default(
            DEFAULT_ADMIN_USERNAME,
            hash_password(DEFAULT_ADMIN_PASSWORD),
            org_id=organization.id,
            name=DEFAULT_ADMIN_NAME,
        )
        session.commit()
    except IntegrityError:
        session.rollback()


def _bootstrap_service_application(session, application_id, name: str, scopes: list[str], secret: str) -> None:
    """Shared by both built-in service-account Applications below: create the row if it doesn't
    exist yet, then (whether just-created or pre-existing) make sure its stored allowed_scopes
    matches the constant — otherwise a scope added to that constant after the row was first
    bootstrapped would never take effect on an existing database, and every token mint would fail
    scope validation until someone noticed and manually fixed the row."""
    repository = ApplicationRepository(session)
    application = repository.get(application_id)
    if application is None:
        try:
            application = repository.create(name, hash_secret(secret), scopes, id=application_id)
            session.commit()
        except IntegrityError:
            session.rollback()
            application = repository.get(application_id)

    if application is not None and set(application.allowed_scopes) != set(scopes):
        repository.update_scopes(application_id, scopes)
        session.commit()


def bootstrap_default_mcp_application(session) -> None:
    """Idempotent: only creates the built-in MCP service-account Application if it doesn't exist
    yet (checked by its fixed id — see app/constants.py). This is what mcp_server/client.py
    authenticates as to call this app's own REST API — no dashboard registration, no env vars.
    See derive_default_mcp_client_secret for why its secret needs no separate storage or handoff
    between this process and mcp_server/server.py's separate process.
    """
    _bootstrap_service_application(
        session,
        DEFAULT_MCP_APPLICATION_ID,
        DEFAULT_MCP_APPLICATION_NAME,
        DEFAULT_MCP_APPLICATION_SCOPES,
        derive_default_mcp_client_secret(config.secret_key),
    )


def bootstrap_default_dashboard_application(session) -> None:
    """Idempotent: only creates the built-in dashboard/workspace service-account Application if it
    doesn't exist yet. This is what app/presentation/routes/workspace.py's POST /dashboard/token
    mints access tokens for, on behalf of an already-logged-in admin session — see
    derive_default_dashboard_client_secret for why its secret needs no separate storage or handoff.
    """
    _bootstrap_service_application(
        session,
        DEFAULT_DASHBOARD_APPLICATION_ID,
        DEFAULT_DASHBOARD_APPLICATION_NAME,
        DEFAULT_DASHBOARD_APPLICATION_SCOPES,
        derive_default_dashboard_client_secret(config.secret_key),
    )
