# Lives in api/deploy/, and the build context is api/ itself (see the `context: ..` in
# api/deploy/docker-compose*.yml, and the CI workflow's `context: api`) — every COPY path below is
# relative to api/, not to this file, and not to the repo root.

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

# Just the requirements file first (not the full `COPY . api` below) so this pip-install layer
# only invalidates when dependencies actually change, not on every source edit.
COPY requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
# Headless Chromium for WebPageFetcher's JS-shell fallback (api/infrastructure/web/fetcher.py) —
# --with-deps pulls in the apt packages Chromium needs on Debian slim, not just the browser binary.
RUN playwright install --with-deps chromium

# The build context IS api/ itself now, so `COPY . api` brings in the whole application —
# migrations/, alembic.ini, wsgi.py, requirements*.txt, VERSION, and mcp_server/ nested inside it
# (see CLAUDE.md) — as one copy, landing at /srv/api to keep every `from api.xxx import` and the
# api.wsgi:app/api.asgi:app gunicorn target unchanged. tests/ and mcp_server/tests/ are excluded
# via Dockerfile.dockerignore, so test code never ships in this image. mcp_server/ is served from
# the same process/port as the rest of the API (api/asgi.py mounts its three MCP tool tiers
# alongside the Flask app) — no separate entrypoint or compose service.
COPY . api
COPY deploy/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

CMD ["./entrypoint.sh"]
