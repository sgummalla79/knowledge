#!/usr/bin/env bash
# Builds and verifies a knowledge image (tagged knowledge:testing) in complete isolation
# from the PROD "api"/"knowledge-db" containers (image knowledge:prod) — never stops,
# rebuilds, or otherwise touches them. See CLAUDE.md, "Docker testing workflow", for why this
# exists.
#
# Run this before deploy/promote-image.sh. If this script fails, the prod containers are
# untouched and nothing needs to be rolled back.
set -euo pipefail
cd "$(dirname "$0")/.."

# Explicit, distinct project name: without it, compose derives the project name from the directory
# ("knowledge"), the same name the prod docker-compose.yml stack uses, which makes compose
# treat the prod "knowledge"/"knowledge-db" containers as orphans of *this* project (harmless
# without --remove-orphans, but confusing). A distinct name keeps the two stacks unambiguously
# separate.
COMPOSE="docker compose -p knowledge-test -f deploy/docker-compose.test.yml"

echo "==> Running pytest (unit + integration; integration tests use ephemeral testcontainers, not this compose stack)"
PYTHON=python3
[ -x .venv/bin/python ] && PYTHON=.venv/bin/python
"$PYTHON" -m pytest tests/

echo "==> Building isolated test image + booting knowledge-test / knowledge-db-test"
$COMPOSE up -d --build

cleanup() {
  echo "==> Tearing down the isolated test stack"
  $COMPOSE down -v
}
trap cleanup EXIT

echo "==> Waiting for knowledge-test to become healthy on :13199"
healthy=false
for _ in $(seq 1 30); do
  if curl -sf http://localhost:13199/health >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 1
done

if [ "$healthy" != true ]; then
  echo "!! knowledge-test never became healthy — check: docker compose -f deploy/docker-compose.test.yml logs api-test"
  exit 1
fi
echo "==> knowledge-test is up"

echo "==> Running end-to-end smoke check"
"$PYTHON" deploy/smoke_test.py

echo "==> Test image is ready to promote: run deploy/promote-image.sh"
