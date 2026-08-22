#!/usr/bin/env bash
# Stops what dev-preview-up.sh started. The Postgres container is stopped, not removed, so its
# data survives — dev-preview-up.sh will just docker start it again next time.
set -uo pipefail

PG_CONTAINER=knowledge-dev-preview
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

echo "==> Postgres (${PG_CONTAINER})"
if docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
  docker stop "$PG_CONTAINER" >/dev/null
  echo "stopped (data preserved — container not removed)"
else
  echo "container not found"
fi
