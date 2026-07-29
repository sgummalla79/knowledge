#!/usr/bin/env bash
# Builds and verifies a knowledge-api image (tagged knowledge-api:testing) in complete isolation
# from the PROD "api"/"knowledge-db" containers (image knowledge-api:prod) — never stops,
# rebuilds, or otherwise touches them. See CLAUDE.md, "Docker testing workflow", for why this
# exists.
#
# Run this before scripts/promote-image.sh. If this script fails, the prod containers are
# untouched and nothing needs to be rolled back.
set -euo pipefail
cd "$(dirname "$0")/.."

# Explicit, distinct project name: without it, compose derives the project name from the directory
# ("knowledge-api"), the same name the prod docker-compose.yml stack uses, which makes compose
# treat the prod "knowledge-api"/"knowledge-db" containers as orphans of *this* project (harmless
# without --remove-orphans, but confusing). A distinct name keeps the two stacks unambiguously
# separate.
COMPOSE="docker compose -p knowledge-api-test -f docker-compose.test.yml"

echo "==> Running pytest (unit + integration; integration tests use ephemeral testcontainers, not this compose stack)"
PYTHON=python3
[ -x .venv/bin/python ] && PYTHON=.venv/bin/python
"$PYTHON" -m pytest tests/

echo "==> Building isolated test image + booting knowledge-api-test / knowledge-db-test"
$COMPOSE up -d --build

cleanup() {
  echo "==> Tearing down the isolated test stack"
  $COMPOSE down -v
}
trap cleanup EXIT

echo "==> Waiting for knowledge-api-test to become healthy on :13199"
healthy=false
for _ in $(seq 1 30); do
  if curl -sf http://localhost:13199/health >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 1
done

if [ "$healthy" != true ]; then
  echo "!! knowledge-api-test never became healthy — check: docker compose -f docker-compose.test.yml logs api-test"
  exit 1
fi
echo "==> knowledge-api-test is up"

echo "==> Running end-to-end smoke check (dashboard login, app registration, library CRUD — proves auth/scopes/DB work, not just that migrations applied)"
"$PYTHON" scripts/smoke_test.py

echo "==> Test image is ready to promote: run scripts/promote-image.sh"
