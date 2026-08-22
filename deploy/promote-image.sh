#!/usr/bin/env bash
# Rebuilds and restarts the PROD "api" container (image knowledge:prod) that rag-desktop actually
# talks to. Only run this after deploy/test-image.sh has passed — see CLAUDE.md, "Docker testing
# workflow".
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Promoting: rebuilding and restarting the prod api container (knowledge:prod)"
# -p knowledge explicit: compose's default project name follows the *first* -f file's
# directory now (deploy/ -> "deploy"), not the repo root dirname ("knowledge") it used to
# derive implicitly — without this it stands up a second, parallel "deploy" project instead of
# recognizing this as the same stack, and collides on the fixed container_names either way.
# No --env-file needed: .env lives in deploy/, right next to docker-compose.yml, which is
# exactly where compose looks by default.
docker compose -p knowledge -f deploy/docker-compose.yml up -d --build api

echo "==> Prod api container updated"
