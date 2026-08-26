"""SQLAlchemy `handle_error` listener that classifies a DB failure by its PostgreSQL SQLSTATE
and logs it as a structured, searchable line — observe-only, never swallows or alters the
exception SQLAlchemy re-raises. Split out from base.py (which only builds the engine/session) to
keep each module to one responsibility.

Exists because of a real production incident (2026-08-24): a leaked, idle-in-transaction
connection held a row lock for 7+ minutes with nothing in the logs showing it — it was only found
by manually inspecting pg_stat_activity on the live database. The lock/statement/idle-in-transaction
timeouts in api/infrastructure/orm/base.py bound how long a fault like that can last; this listener
makes sure it's a visible, greppable log line the moment it happens instead of a silent stall.

Never logs SQL text or parameters — only the coarse operation keyword (the first SQL token) — same
restraint this app's request logging already applies to query strings/paths.
"""

import logging

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import ExceptionContext
from sqlalchemy.exc import StatementError

from api.constants import SQLSTATE_ERROR_LEVEL_CODES, SQLSTATE_FAULT_NAMES, SQLSTATE_QUERY_CANCELED

logger = logging.getLogger(__name__)


def _operation_keyword(statement: str | None) -> str:
    stripped = (statement or "").lstrip()
    if not stripped:
        return "UNKNOWN"
    return stripped.split(None, 1)[0].upper()


def sqlstate_of_error(error) -> str | None:
    """Extracts a PostgreSQL SQLSTATE from either shape a caller might be holding: a raw DBAPI
    exception (asyncpg exposes it as `.sqlstate`; psycopg2, this app's driver, as `.pgcode`), or a
    SQLAlchemy `StatementError` wrapping one (`.orig`). Returns None for anything else, including
    `None` itself, so callers can pass a possibly-absent original exception without a guard.
    """
    if error is None:
        return None
    orig = getattr(error, "orig", error)
    if orig is None:
        return None
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _sqlstate_of(exception_context: ExceptionContext) -> str | None:
    return sqlstate_of_error(exception_context.original_exception)


def safe_error_message(error: BaseException) -> str:
    """A message safe to persist (e.g. ingestion_jobs.error_message) or show a user, for any
    exception a caller might catch. A SQLAlchemy `StatementError` (OperationalError,
    IntegrityError, ...) is the one case that isn't already safe as-is: its own str() embeds the
    complete failed SQL statement and every bound parameter -- for chunk_repository.bulk_create,
    that means every chunk's full embedding vector in the batch, confirmed in production
    (2026-08-25) to produce a multi-kilobyte wall of floats surfaced straight to the upload UI.
    Every other exception (a domain ValidationError, etc.) already carries a human-authored
    message and is returned via str() unchanged.
    """
    if not isinstance(error, StatementError):
        return str(error)
    if sqlstate_of_error(error) == SQLSTATE_QUERY_CANCELED:
        return "Database timed out while saving this document. Please retry the upload."
    return "A database error occurred while saving this document. Please retry the upload."


def _handle_error(exception_context: ExceptionContext) -> None:
    sqlstate = _sqlstate_of(exception_context)
    fault = SQLSTATE_FAULT_NAMES.get(sqlstate) if sqlstate else None
    if fault is None:
        return
    level = logging.ERROR if sqlstate in SQLSTATE_ERROR_LEVEL_CODES else logging.WARNING
    logger.log(
        level,
        "Database fault: %s",
        fault,
        extra={
            "sqlstate": sqlstate,
            "db_fault": fault,
            "operation": _operation_keyword(exception_context.statement),
        },
    )


def register_db_fault_logging(engine: Engine) -> None:
    """Call once against the engine at creation (api/infrastructure/orm/base.py) — registering
    twice would log every fault twice."""
    event.listen(engine, "handle_error", _handle_error)
