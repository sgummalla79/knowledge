#!/usr/bin/env bash
# Stops what dev-preview-up.sh started. The Postgres container is stopped, not removed, so its
# data survives — dev-preview-up.sh will just `docker compose up -d` it again next time.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -p knowledge-dev-preview -f $REPO_ROOT/deploy/docker-compose.dev-preview.yml"
FLASK_PID_FILE=/tmp/workspace-preview.pid
VITE_PID_FILE=/tmp/workspace-preview-vite.pid

_stop_pid_file() {
  local label="$1" pid_file="$2"
  echo "==> $label"
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      echo "stopped (pid $pid)"
    else
      echo "no process at pid $pid (already stopped)"
    fi
    rm -f "$pid_file"
  else
    echo "no PID file, nothing to stop"
  fi
}

_stop_pid_file "backend" "$FLASK_PID_FILE"
_stop_pid_file "frontend (Vite dev server)" "$VITE_PID_FILE"

echo "==> Postgres (knowledge-dev-preview)"
$COMPOSE stop
