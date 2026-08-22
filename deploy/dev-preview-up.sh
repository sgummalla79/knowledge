#!/usr/bin/env bash
# Starts the local dev-preview stack: Postgres/pgvector in Docker, the Flask backend and the
# built frontend running natively (no app Docker image). Conventions match CLAUDE.md's
# "Local dev preview" table — keep this in sync with dev-preview-down.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_CONTAINER=knowledge-dev-preview
PG_PORT=15432
PG_IMAGE=pgvector/pgvector:pg16
FLASK_PORT=15100
SECRET_KEY=dev-preview-secret
DATABASE_URL="postgresql://rag:rag@127.0.0.1:${PG_PORT}/rag"
PID_FILE=/tmp/workspace-preview.pid
LOG_FILE=/tmp/knowledge-dev-preview-flask.log
VENV_PY="$REPO_ROOT/api/.venv/bin/python"

echo "==> Postgres (${PG_CONTAINER})"
if docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
  if [ "$(docker inspect -f '{{.State.Running}}' "$PG_CONTAINER")" != "true" ]; then
    docker start "$PG_CONTAINER" >/dev/null
    echo "started existing container"
  else
    echo "already running"
  fi
else
  echo "container not found — pulling ${PG_IMAGE} and creating it"
  docker run -d --name "$PG_CONTAINER" -p "${PG_PORT}:5432" \
    -e POSTGRES_DB=rag -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag \
    "$PG_IMAGE" >/dev/null
fi

echo "==> waiting for Postgres to accept connections"
ready=false
for _ in $(seq 1 30); do
  if docker exec "$PG_CONTAINER" pg_isready -U rag >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [ "$ready" != true ]; then
  echo "Postgres did not become ready in time" >&2
  exit 1
fi

if [ ! -x "$VENV_PY" ]; then
  echo "==> creating api/.venv"
  python3 -m venv "$REPO_ROOT/api/.venv"
  "$VENV_PY" -m pip install -q -r "$REPO_ROOT/api/requirements.txt" -r "$REPO_ROOT/api/requirements-dev.txt"
fi

echo "==> running migrations"
DATABASE_URL="$DATABASE_URL" SECRET_KEY="$SECRET_KEY" \
  "$VENV_PY" -m alembic -c "$REPO_ROOT/api/alembic.ini" upgrade head

if [ ! -d "$REPO_ROOT/webui/node_modules" ]; then
  echo "==> installing frontend dependencies"
  (cd "$REPO_ROOT/webui" && npm install)
fi

echo "==> building frontend"
(cd "$REPO_ROOT/webui" && npm run build)

echo "==> backend"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "already running (pid $(cat "$PID_FILE"))"
else
  DATABASE_URL="$DATABASE_URL" SECRET_KEY="$SECRET_KEY" \
    nohup "$VENV_PY" -m flask --app api.wsgi run --port "$FLASK_PORT" \
    > "$LOG_FILE" 2>&1 &
  disown
  echo $! > "$PID_FILE"
  sleep 1
  echo "started (pid $(cat "$PID_FILE")), logging to $LOG_FILE"
fi

echo
echo "Ready: http://127.0.0.1:${FLASK_PORT}/sign-in"
