from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from api.config import config
from api.infrastructure.orm.db_fault_logging import register_db_fault_logging

# pool_pre_ping: validates a pooled connection (cheap SELECT 1) before handing it to app code,
# transparently reconnecting if it's gone stale -- guards against the VPS's network layer silently
# dropping idle connections (common NAT/conntrack behavior), which otherwise hangs the first query
# on a dead connection for up to pool_timeout (default 30s) with no visible error.
# pool_recycle: proactively recycles connections older than 30 minutes, ahead of whatever the
# host's own idle-connection timeout turns out to be.
# connect_args: connect_timeout so a stuck new-connection attempt fails fast instead of hanging.
# The `options` string sets three per-connection Postgres session timeouts via psycopg2's startup
# param (see api/constants.py's DB_*_TIMEOUT_MS_DEFAULT comment for why all three, and
# api/config.py for how each is env-overridable): statement_timeout (a query stuck *executing* too
# long) and lock_timeout (a query stuck *waiting to acquire a lock* too long) were already
# necessary; idle_in_transaction_session_timeout closes the gap those two leave open -- a session
# that opened a transaction and then went idle mid-transaction, holding whatever locks it already
# has, without executing anything at all. That exact state caused a real production outage
# (2026-08-24): a leaked connection sat idle-in-transaction for 7+ minutes, undetected, blocking
# every other request that touched the same row, until it was found and killed by hand.
engine = create_engine(
    config.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    # Sized down from SQLAlchemy's own defaults (5+10=15) now that multiple processes share one
    # Postgres max_connections budget -- see api/constants.py's DB_POOL_SIZE_DEFAULT comment.
    pool_size=config.db_pool_size,
    max_overflow=config.db_max_overflow,
    connect_args={
        "connect_timeout": 10,
        "options": (
            f"-c statement_timeout={config.db_statement_timeout_ms} "
            f"-c lock_timeout={config.db_lock_timeout_ms} "
            f"-c idle_in_transaction_session_timeout={config.db_idle_in_transaction_timeout_ms}"
        ),
    },
)
register_db_fault_logging(engine)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
