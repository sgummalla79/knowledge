#!/usr/bin/env bash
# Stops what dev-preview-up.sh started. The Postgres container is stopped, not removed, so its
# data survives — dev-preview-up.sh will just `docker compose up -d` it again next time.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -p knowledge-dev-preview -f $REPO_ROOT/deploy/docker-compose.dev-preview.yml"
PID_FILE=/tmp/workspace-preview.pid

echo "==> backend"
if [ -f "$PID_FILE" ]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "stopped (pid $pid)"
  else
    echo "no process at pid $pid (already stopped)"
  fi
  rm -f "$PID_FILE"
else
  echo "no PID file, nothing to stop"
fi

echo "==> Postgres (knowledge-dev-preview)"
$COMPOSE stop
