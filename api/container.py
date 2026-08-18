from uuid import UUID

from flask import g
from sqlalchemy import text

from api.infrastructure.orm import SessionLocal


def get_session():
    if "db_session" not in g:
        g.db_session = SessionLocal()
    return g.db_session


def set_rls_session_vars(org_id: UUID, user_id: UUID) -> None:
    """Sets the transaction-scoped `app.org_id`/`app.user_id` the RLS policies in migration 0001
    check (`current_setting('app.org_id')`/`'app.user_id'`) — via `set_config(..., true)` rather
    than `SET LOCAL app.org_id = :org_id` directly, since Postgres doesn't accept a bind parameter
    as a SET command's value. `true` (the third arg) makes it transaction-local, matching SET
    LOCAL's lifetime — this app's one request = one transaction (commit happens at teardown), so
    it holds for the whole request. Currently a no-op in terms of actual enforcement (see
    docs/DATA_MODEL.md's Row-level security section — the app's DB role still owns every table and
    is exempt from its own RLS policies), but calling it here now means a later phase only has to
    add the restricted role, not also find every place a request resolves org_id/user_id."""
    session = get_session()
    session.execute(
        text("SELECT set_config('app.org_id', :org_id, true), set_config('app.user_id', :user_id, true)"),
        {"org_id": str(org_id), "user_id": str(user_id)},
    )


def rollback_session_if_active():
    """Roll back any pending, uncommitted work for this request's session.

    Registered error handlers turn every exception (DomainError, validation errors, etc.)
    into a normal Response, so by the time teardown_session runs, Flask sees no exception and
    would otherwise commit whatever partial flush happened before the error. Error handlers
    call this first so teardown's commit-on-no-exception is always safe.
    """
    session = g.get("db_session")
    if session is not None:
        session.rollback()


def teardown_session(exception=None):
    session = g.pop("db_session", None)
    if session is not None:
        if exception is None:
            session.commit()
        else:
            session.rollback()
        session.close()
