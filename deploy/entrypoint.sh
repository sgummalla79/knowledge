#!/bin/sh
set -e

alembic upgrade head

# MCP HTTP server: a genuine long-running process now (streamable-http, not exec'd on demand per
# connection like the old stdio transport). Loopback-only reachability is enforced by
# deploy/docker-compose.yml's host-side port mapping, not an in-container bind restriction — see
# mcp_server/server.py for why. Backgrounded so gunicorn stays this container's foreground process
# and keeps receiving signals correctly. Authenticates to the API below as the built-in MCP
# service-account Application (bootstrapped by app/infrastructure/auth/bootstrap.py the first time
# gunicorn's create_app() runs) — no credentials to configure here.
python -m mcp_server.server &

# --workers 1 --worker-class gthread --threads: previously plain sync with an implicit single
# worker, which meant any one stuck/idle connection (no data sent within --timeout, the default
# 30s) blocked the entire API until gunicorn killed and restarted that worker — a real recurring
# outage once a persistent client (streamable-http MCP sessions hold connections open) was in the
# picture. Multiple *processes* (--workers > 1) would isolate that, but app/application/job_store.py
# and app/rate_limit.py both keep their state in a plain in-memory dict scoped to one process
# (JobStore's own docstring says as much) — multiple worker processes would silently split that
# state, so a job-status poll landing on a different worker than the one that started the job would
# wrongly 404. Threads within a single process share that state correctly while still handling a
# stuck connection on one thread without blocking the others — same fix, without the split-state bug.
exec gunicorn -b 0.0.0.0:${PORT:-13102} --workers 1 --worker-class gthread --threads ${GUNICORN_THREADS:-4} --access-logfile - --error-logfile - --log-level ${LOG_LEVEL:-info} wsgi:app
