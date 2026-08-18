from sqlalchemy.exc import IntegrityError

from app.domain.errors import ConflictError
from app.constants import (
    DEFAULT_ADMIN_NAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ORGANIZATION_NAME,
    DEFAULT_ORGANIZATION_SLUG,
)
from app.infrastructure.auth.passwords import hash_password
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
