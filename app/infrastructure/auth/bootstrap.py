from sqlalchemy.exc import IntegrityError

from app.constants import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from app.infrastructure.auth.passwords import hash_password
from app.infrastructure.repositories.user_repository import UserRepository


def bootstrap_default_admin(session) -> None:
    """Idempotent: only creates the default admin if no user exists yet.

    Takes an explicit session rather than app.container.get_session() (which needs an active
    Flask request context via flask.g) — this runs once at app startup, before any request, and
    is also called directly by integration tests that need a seeded user without going through
    create_app(). Tolerates a duplicate-insert race (unique constraint on username) in case
    multiple workers ever start concurrently — not currently possible with this app's single-worker
    gunicorn config, but harmless and correct to guard against regardless.
    """
    repository = UserRepository(session)
    if repository.get() is not None:
        return
    try:
        repository.create_default(DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD))
        session.commit()
    except IntegrityError:
        session.rollback()
