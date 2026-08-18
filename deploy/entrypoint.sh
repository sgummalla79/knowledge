#!/bin/sh
set -e

alembic -c api/alembic.ini upgrade head

# --workers 1 --worker-class gthread --threads: previously plain sync with an implicit single
# worker, which meant any one stuck/idle connection (no data sent within --timeout, the default
# 30s) blocked the entire API until gunicorn killed and restarted that worker. Multiple
# *processes* (--workers > 1) would isolate that, but api/application/job_store.py and
# api/rate_limit.py both keep their state in a plain in-memory dict scoped to one process
# (JobStore's own docstring says as much) — multiple worker processes would silently split that
# state, so a job-status poll landing on a different worker than the one that started the job would
# wrongly 404. Threads within a single process share that state correctly while still handling a
# stuck connection on one thread without blocking the others — same fix, without the split-state bug.
exec gunicorn -b 0.0.0.0:${PORT:-13102} --workers 1 --worker-class gthread --threads ${GUNICORN_THREADS:-4} --access-logfile - --error-logfile - --log-level ${LOG_LEVEL:-info} api.wsgi:app
