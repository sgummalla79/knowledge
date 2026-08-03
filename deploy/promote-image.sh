#!/usr/bin/env bash
# Rebuilds and restarts the PROD "api" container (image knowledge-api:prod) that rag-desktop and
# MCP clients actually talk to. Only run this after deploy/test-image.sh has passed — see
# CLAUDE.md, "Docker testing workflow".
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Promoting: rebuilding and restarting the prod api container (knowledge-api:prod)"
# -p knowledge-api explicit: compose's default project name follows the *first* -f file's
# directory now (deploy/ -> "deploy"), not the repo root dirname ("knowledge-api") it used to
# derive implicitly — without this it stands up a second, parallel "deploy" project instead of
# recognizing this as the same stack, and collides on the fixed container_names either way.
# --env-file explicit for the same reason: the default .env lookup follows that same directory.
docker compose -p knowledge-api -f deploy/docker-compose.yml --env-file .env up -d --build api

echo "==> Prod api container updated"
