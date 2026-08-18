from flask import g

from app.infrastructure.auth.bootstrap import bootstrap_default_organization
from app.infrastructure.orm import SessionLocal
from app.infrastructure.repositories.user_repository import UserRepository


def get_session():
    if "db_session" not in g:
        g.db_session = SessionLocal()
    return g.db_session


def get_default_org_id():
    """Interim only: resolves the single bootstrap organization, since there is currently no
    auth layer to resolve "which org is this request for" from a real identity. Every route uses
    this in place of an authenticated org_id until a standalone auth/identity service exists and
    is wired in — at that point this goes away and org_id comes from the resolved caller instead."""
    if "default_org_id" not in g:
        g.default_org_id = bootstrap_default_organization(get_session()).id
    return g.default_org_id


def get_default_user_id():
    """Interim only, mirroring get_default_org_id() above: resolves the single bootstrapped admin
    user for routes that need an owner_id/actor (e.g. document ingestion) but have no authenticated
    caller to take it from yet. Goes away alongside get_default_org_id() once a real auth layer
    resolves the acting user from the request itself."""
    if "default_user_id" not in g:
        g.default_user_id = UserRepository(get_session()).get().id
    return g.default_user_id


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
