# Lives in deploy/ but the build context is the repo root (see the `context: ..` in
# deploy/docker-compose*.yml) — every COPY path below is relative to that root, not to this file.

# Builds the /workspace SPA (webui/) to static assets — done in its own stage so the final image
# never needs a Node runtime, just the built output. See webui/vite.config.ts: base/outDir are set
# so this lands exactly where app/presentation/routes/workspace.py expects to find it.
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Headless Chromium for WebPageFetcher's JS-shell fallback (app/infrastructure/web/fetcher.py) —
# --with-deps pulls in the apt packages Chromium needs on Debian slim, not just the browser binary.
RUN playwright install --with-deps chromium

COPY app app
COPY migrations migrations
COPY alembic.ini wsgi.py VERSION ./
COPY deploy/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
COPY --from=webui-build /app/static/workspace app/static/workspace

CMD ["./entrypoint.sh"]
