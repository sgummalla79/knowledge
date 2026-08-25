#!/usr/bin/env bash
# Starts the local dev-preview stack: Postgres/pgvector via docker compose
# (deploy/docker-compose.dev-preview.yml), the Flask backend, and webui/'s own Vite dev server —
# three separate processes/containers, matching this repo's standalone-API architecture (see
# CLAUDE.md session history item 34: this API renders no HTML/SPA of any kind, so webui/ must run
# on its own, not built-and-served-by-Flask as it used to be). Conventions match CLAUDE.md's
# "Local dev preview" table — keep this in sync with dev-preview-down.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -p knowledge-dev-preview -f $REPO_ROOT/deploy/docker-compose.dev-preview.yml"
PG_PORT=15432
FLASK_PORT=15100
VITE_PORT=5173
SECRET_KEY=dev-preview-secret
DATABASE_URL="postgresql://rag:rag@127.0.0.1:${PG_PORT}/rag"
# UPLOADS_DIR defaults to /data/uploads (the real k8s mount path) -- not writable/meaningful on a
# dev machine, so this flow overrides it to a local throwaway directory instead (see
# docs/UPLOAD_STORAGE_REDESIGN.md). Note: dev-preview does not run api/ingestion_worker/ (only
# Flask + Vite), so an uploaded file lands here and its job stays "queued" -- a pre-existing gap
# unrelated to this variable, not something this script fixes.
UPLOADS_DIR=/tmp/knowledge-dev-preview-uploads
FLASK_PID_FILE=/tmp/workspace-preview.pid
FLASK_LOG_FILE=/tmp/knowledge-dev-preview-flask.log
VITE_PID_FILE=/tmp/workspace-preview-vite.pid
VITE_LOG_FILE=/tmp/knowledge-dev-preview-vite.log
VENV_PY="$REPO_ROOT/api/.venv/bin/python"

echo "==> Postgres (knowledge-dev-preview)"
$COMPOSE up -d

echo "==> waiting for Postgres to accept connections"
ready=false
for _ in $(seq 1 30); do
  if $COMPOSE exec -T knowledge-dev-preview pg_isready -U rag >/dev/null 2>&1; then
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

echo "==> backend"
if [ -f "$FLASK_PID_FILE" ] && kill -0 "$(cat "$FLASK_PID_FILE")" 2>/dev/null; then
  echo "already running (pid $(cat "$FLASK_PID_FILE"))"
else
  DATABASE_URL="$DATABASE_URL" SECRET_KEY="$SECRET_KEY" UPLOADS_DIR="$UPLOADS_DIR" \
    nohup "$VENV_PY" -m flask --app api.wsgi run --port "$FLASK_PORT" \
    > "$FLASK_LOG_FILE" 2>&1 &
  disown
  echo $! > "$FLASK_PID_FILE"
  sleep 1
  echo "started (pid $(cat "$FLASK_PID_FILE")), logging to $FLASK_LOG_FILE"
fi

echo "==> frontend (Vite dev server)"
if [ -f "$VITE_PID_FILE" ] && kill -0 "$(cat "$VITE_PID_FILE")" 2>/dev/null; then
  echo "already running (pid $(cat "$VITE_PID_FILE"))"
else
  # VITE_API_BASE_URL overrides webui/.env.development's own default (which points at the
  # verify/"prod" API port, 13102 — see CLAUDE.md session history item 35) to this Flask instance.
  (cd "$REPO_ROOT/webui" && VITE_API_BASE_URL="http://127.0.0.1:${FLASK_PORT}" \
    nohup npm run dev > "$VITE_LOG_FILE" 2>&1 &
   disown
   echo $! > "$VITE_PID_FILE")
  sleep 1
  echo "started (pid $(cat "$VITE_PID_FILE")), logging to $VITE_LOG_FILE"
fi

echo
echo "Ready: http://127.0.0.1:${VITE_PORT}/sign-in"
