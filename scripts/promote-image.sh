#!/usr/bin/env bash
# Rebuilds and restarts the PROD "api" container (image knowledge-api:prod) that rag-desktop and
# MCP clients actually talk to. Only run this after scripts/test-image.sh has passed — see
# CLAUDE.md, "Docker testing workflow".
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Promoting: rebuilding and restarting the prod api container (knowledge-api:prod)"
docker compose up -d --build api

# ollama-pull is a one-shot init container (pulls the embedding model, then exits) that api's
# `depends_on: condition: service_completed_successfully` already waits on before starting — by
# the time `up` above returns, it has finished. Compose has no declarative "auto-remove on exit"
# for `up`-managed services (that's a `docker run --rm` behavior, not part of the Compose
# Specification), so it's removed explicitly here rather than left sitting in an Exited state.
# `rm -f`: `-f` skips the interactive "are you sure" prompt (`rm` alone only ever touches stopped
# containers, so this isn't force-killing anything running) — needed since this runs non-interactively.
docker compose rm -f ollama-pull

echo "==> Prod api container updated"
