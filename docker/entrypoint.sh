#!/bin/sh
set -e

alembic upgrade head

# MCP HTTP server: a genuine long-running process now (streamable-http, not exec'd on demand per
# connection like the old stdio transport). Loopback-only reachability is enforced by
# docker-compose.yml's host-side port mapping, not an in-container bind restriction — see
# mcp_server/server.py for why. Backgrounded so gunicorn stays this container's foreground process
# and keeps receiving signals correctly. Authenticates to the API below as the built-in MCP
# service-account Application (bootstrapped by app/infrastructure/auth/bootstrap.py the first time
# gunicorn's create_app() runs) — no credentials to configure here.
python -m mcp_server.server &

# --workers: previously implicitly 1 (gunicorn's sync-worker default), which meant any single
# stuck/idle connection (no data sent within --timeout, the default 30s) blocked the entire API —
# not just that one request — until gunicorn killed and restarted the worker. Harmless with sparse
# manual traffic, but a real recurring outage once a persistent client (streamable-http MCP
# sessions hold connections open) is in the picture. Multiple workers isolate a stuck connection
# to one worker instead of the whole process.
exec gunicorn -b 0.0.0.0:${PORT:-13102} --workers ${GUNICORN_WORKERS:-3} --access-logfile - --error-logfile - --log-level ${LOG_LEVEL:-info} wsgi:app
