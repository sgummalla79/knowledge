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
# --workers 3 (was pinned to 1 until this app's ingestion-worker Release 2, see this repo's
# session history): the only state that ever forced --workers 1 was api/application/job_store.py/
# crawl_job_store.py, both deleted now that ingestion runs in its own standalone process
# (api/ingestion_worker/) reading/writing ingestion_jobs in Postgres instead of an in-memory dict
# scoped to one process. api/rate_limit.py's in-memory storage stays as a deliberate, accepted
# tradeoff (see that file's own comment) -- it never needed cross-worker consistency, just
# per-worker abuse-prevention. MCP session state used to be assumed safe the same way ("a gunicorn
# worker owns whichever persistent connections it accepted for their entire lifetime, the same way
# a k8s Service pins a live connection to one pod") -- that reasoning holds for a direct
# client-to-pod connection but not through Traefik, which pools its own backend connections to the
# Service independently of the client's connection to Traefik itself, so a session minted on one
# worker had no guarantee of landing back there on the next request. Confirmed in production
# (repeated calls against one real session flip-flopped 200/404 "Session not found") and fixed by
# making every MCP tier stateless (stateless_http=True, api/mcp_server/server.py) instead -- no
# session id, no per-process session store, nothing for --workers or replica count to fragment. 3
# is not a hard limit, just matches this box's
# real capacity (2 vCPU) with headroom shared across api/deploy/k3s/02-api.yaml's replica count --
# see api/constants.py's DB_POOL_SIZE_DEFAULT comment for how the DB connection budget was sized
# to match total processes (replicas x workers, plus the ingestion worker).
#
# --log-level stays as-is (gunicorn's own flag, case-insensitive) even though this app's LOG_LEVEL
# convention is uppercase — that's a gunicorn property, not a uvicorn one, and gunicorn remains the
# outer process manager even when running an ASGI worker.
exec gunicorn -b 0.0.0.0:${PORT:-13102} --workers 3 -k uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - --log-level ${LOG_LEVEL:-info} api.asgi:app
