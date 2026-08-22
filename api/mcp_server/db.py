from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import text

from api.infrastructure.orm import SessionLocal


@contextmanager
def session_scope():
    """This process has no Flask request/g to hang a session off (api.container.get_session()'s
    approach), so each tool call — and each token verification — opens and closes its own,
    committing on success and rolling back on any exception, mirroring
    api.container.teardown_session's commit-on-no-exception behavior."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def set_rls_session_vars(session, org_id: UUID, user_id: UUID) -> None:
    """Same SQL as api.container.set_rls_session_vars, duplicated rather than imported — that
    function is Flask-g-coupled (calls get_session() internally instead of accepting one), and
    this process has no Flask request context to satisfy it."""
    session.execute(
        text("SELECT set_config('app.org_id', :org_id, true), set_config('app.user_id', :user_id, true)"),
        {"org_id": str(org_id), "user_id": str(user_id)},
    )
