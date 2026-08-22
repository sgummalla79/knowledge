# Lives in deploy/ but the build context is the repo root (see the `context: ..` in
# deploy/docker-compose*.yml) — every COPY path below is relative to that root, not to this file.

# API-only image — no Node/webui build stage. The React SPA (webui/) is a separate deployable
# (its own image, own build step), not bundled in here; this API serves JSON only, over any
# subdomain/origin, to any client (browser via session cookie, Postman/scripts via OAuth2 bearer
# token — see this repo's Phase A history for why the two were split).
#
# Pinned to bookworm (not the floating "slim" tag, which has moved to trixie) — playwright
# install --with-deps below doesn't yet recognize trixie's apt package names (e.g. ttf-unifont
# was renamed/split there) and fails; bookworm is a Debian release Playwright fully supports.
FROM python:3.12-slim-bookworm

WORKDIR /srv
ENV PYTHONPATH=/srv

# Just the requirements file first (not the full `COPY api api` below) so this pip-install layer
# only invalidates when dependencies actually change, not on every source edit.
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
# Headless Chromium for WebPageFetcher's JS-shell fallback (api/infrastructure/web/fetcher.py) —
# --with-deps pulls in the apt packages Chromium needs on Debian slim, not just the browser binary.
RUN playwright install --with-deps chromium

# api/ carries its own migrations/, alembic.ini, wsgi.py, requirements*.txt, and mcp_server/
# nested inside it (see CLAUDE.md) — one COPY brings in all of it. api/tests/ and
# api/mcp_server/tests/ are excluded via .dockerignore, so test code never ships in this image.
# mcp_server/ is served from the same process/port as the rest of the API (api/asgi.py mounts its
# three MCP tool tiers alongside the Flask app) — no separate entrypoint or compose service.
COPY api api
COPY VERSION .
COPY deploy/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

CMD ["./entrypoint.sh"]
