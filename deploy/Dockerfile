# Lives in deploy/ but the build context is the repo root (see the `context: ..` in
# deploy/docker-compose*.yml) — every COPY path below is relative to that root, not to this file.

# Builds the /workspace SPA (webui/) to static assets — done in its own stage so the final image
# never needs a Node runtime, just the built output. See webui/vite.config.ts: base/outDir are set
# so this lands exactly where api/presentation/routes/workspace.py expects to find it.
FROM node:22-slim AS webui-build
WORKDIR /webui
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui .
RUN npm run build

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
COPY --from=webui-build /api/static/workspace api/static/workspace

CMD ["./entrypoint.sh"]
