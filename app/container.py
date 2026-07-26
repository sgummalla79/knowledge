from flask import g

from app.infrastructure.orm import SessionLocal


def get_session():
    if "db_session" not in g:
        g.db_session = SessionLocal()
    return g.db_session


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
