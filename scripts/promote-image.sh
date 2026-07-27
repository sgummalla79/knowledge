#!/usr/bin/env bash
# Rebuilds and restarts the PROD "api" container (image knowledge-api:prod) that rag-desktop and
# MCP clients actually talk to. Only run this after scripts/test-image.sh has passed — see
# CLAUDE.md, "Docker testing workflow".
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Promoting: rebuilding and restarting the prod api container (knowledge-api:prod)"
docker compose up -d --build api

echo "==> Prod api container updated"
