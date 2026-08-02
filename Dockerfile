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
COPY mcp_server mcp_server
COPY migrations migrations
COPY alembic.ini wsgi.py ./
COPY docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

CMD ["./entrypoint.sh"]
