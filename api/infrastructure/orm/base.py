from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from api.config import config

# pool_pre_ping: validates a pooled connection (cheap SELECT 1) before handing it to app code,
# transparently reconnecting if it's gone stale -- guards against the VPS's network layer silently
# dropping idle connections (common NAT/conntrack behavior), which otherwise hangs the first query
# on a dead connection for up to pool_timeout (default 30s) with no visible error.
# pool_recycle: proactively recycles connections older than 30 minutes, ahead of whatever the
# host's own idle-connection timeout turns out to be.
# connect_args: connect_timeout so a stuck new-connection attempt fails fast instead of hanging;
# statement_timeout (via psycopg2's `options` connect param) so a genuinely stuck query errors out
# instead of hanging indefinitely and tying up one of a2wsgi's shared WSGI worker threads.
engine = create_engine(
    config.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"connect_timeout": 10, "options": "-c statement_timeout=15000"},
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
