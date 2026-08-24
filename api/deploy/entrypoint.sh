#!/bin/sh
set -e

alembic -c api/alembic.ini upgrade head

# -k uvicorn.workers.UvicornWorker, api.asgi:app (not api.wsgi:app): the api process now also
# serves the three MCP tool tiers (api/mcp_server/) natively over ASGI, merged with the Flask REST API
# via a2wsgi.WSGIMiddleware — see api/asgi.py and api/presentation/web/asgi_bridge.py. --threads
# doesn't apply to an ASGI worker (no thread pool); UvicornWorker's async event loop gives the same
# "one stuck/idle connection doesn't block every other request" property --worker-class gthread
# --threads used to, without needing multiple threads to do it.
#
# --workers stays 1 regardless: api/application/job_store.py and api/rate_limit.py both keep their
# state in a plain in-memory dict scoped to one process (JobStore's own docstring says as much) —
# multiple worker *processes* would silently split that state, so a job-status poll landing on a
# different worker than the one that started the job would wrongly 404. Now also true of MCP
# session state, for the same reason.
#
# --log-level stays as-is (gunicorn's own flag, case-insensitive) even though this app's LOG_LEVEL
# convention is uppercase — that's a gunicorn property, not a uvicorn one, and gunicorn remains the
# outer process manager even when running an ASGI worker.
exec gunicorn -b 0.0.0.0:${PORT:-13102} --workers 1 -k uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - --log-level ${LOG_LEVEL:-info} api.asgi:app
