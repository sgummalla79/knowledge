# sgummalla/knowledge-api — Docker Hub Overview

This file is the source of truth for the **Overview** tab on
[hub.docker.com/r/sgummalla/knowledge-api](https://hub.docker.com/r/sgummalla/knowledge-api).
Docker Hub does not pull this automatically — after editing this file, paste its contents into
the Docker Hub repo's Overview editor by hand. Keep it in sync whenever a change in this repo
would affect what a first-time puller of the image needs to know (new/renamed env vars, routes,
ports, volumes, auth flow).

---

## Description

A self-hosted RAG (retrieval-augmented generation) backend: create knowledge libraries, ingest
documents (Markdown, plain text, PDF), and retrieve relevant chunks via hybrid (dense + sparse)
vector search. Every resource route requires a scoped OAuth2 bearer token — there is no
unauthenticated or static-API-key access.

## Key Features

- Hybrid vector search (pgvector dense + keyword sparse, fused via reciprocal rank fusion)
- OAuth2 authentication — `client_credentials`, `refresh_token`, and PKCE `authorization_code`
  grants, all via `POST /oauth/token`
- Bundled MCP (Model Context Protocol) server (`list_libraries` / `query_library` tools) over
  streamable-HTTP, for MCP clients like Claude Code — loopback-only, and authenticates to the
  API automatically (no credentials to configure)
- React SPA admin UI served from the same image — no separate frontend container
- Multi-arch: `linux/amd64` and `linux/arm64`

## Requirements

- Docker and Docker Compose
- A PostgreSQL database with the pgvector extension (`pgvector/pgvector:pg16` is what this image
  is tested against)

## Environment Variables

| Variable          | Required | Default | Purpose                                            |
|--------------------|----------|---------|-----------------------------------------------------|
| `DATABASE_URL`     | Yes      | —       | PostgreSQL connection string                        |
| `SECRET_KEY`       | Yes      | —       | Signs JWTs, session cookies, and the bundled MCP client's derived secret |
| `PORT`             | No       | 13102   | REST API port (gunicorn binds `0.0.0.0:$PORT`)       |
| `MCP_HTTP_PORT`    | No       | 13103   | MCP server port                                      |
| `LOG_LEVEL`        | No       | INFO    | gunicorn log level                                   |
| `GUNICORN_THREADS` | No       | 4       | Threads per gunicorn worker (the process runs a single worker with multiple threads by design — see note below) |

The container runs `alembic upgrade head` automatically on startup — no manual migration step.

> **Why one worker, many threads:** job status and rate-limit state are kept in an in-memory dict
> scoped to a single process. Multiple worker *processes* would silently split that state (a
> job-status poll could 404 by landing on the wrong worker); threads within one process share it
> correctly while still avoiding one stuck connection blocking every other request.

## Ports & Volumes

- **API port:** `13102` (or `$PORT`) — publish this to the host normally.
- **MCP port:** `13103` (or `$MCP_HTTP_PORT`) — publish it **loopback-bound**
  (`127.0.0.1:13103:13103`), it's meant to be reachable only from the host machine, never off it.
- **Volume:** mount `/var/lib/postgresql/data` on the **Postgres** container for persistence
  (the API container itself is stateless).

## Quick Start (docker-compose)

```yaml
services:
  knowledge-db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: rag
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - knowledge-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag"]
      interval: 5s
      timeout: 5s
      retries: 10

  api:
    image: sgummalla/knowledge-api:latest
    depends_on:
      knowledge-db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://rag:${POSTGRES_PASSWORD}@knowledge-db:5432/rag
      SECRET_KEY: ${SECRET_KEY}
    ports:
      - "13102:13102"
      - "127.0.0.1:13103:13103"

volumes:
  knowledge-db-data:
```

Set `POSTGRES_PASSWORD` and `SECRET_KEY` in a `.env` file next to this compose file (or export
them), then `docker compose up -d`. Check `http://localhost:13102/health` for a `200` once it's
up.

## The Admin UI (React SPA)

This image bundles a full React single-page app — there's no separate frontend container or build
step, it's served from the same `api` container and the same port (`13102`). It's the primary way
to administer the instance; the raw HTTP API underneath is what it (and everything else — the MCP
server, external clients) calls.

- **`/login`** — session-cookie login (separate from the bearer-token API), forced password
  change on first login as `admin` / `admin`.
- **`/workspace`** — the main app: create libraries, ingest documents, run queries.
- **`/settings`** and its sub-pages (rail on the left once you're logged in):
  - **Providers** (`/settings`, the settings index) — configure and enable/disable embedding
    providers. Covered in detail below.
  - **Applications** (`/settings/applications`) — register OAuth2 clients (client id + secret,
    shown once) for anything that needs to call the bearer-token API from outside the browser;
    view scopes, revoke tokens, delete. Read-only list plus a registration form under the hood —
    see the next section for getting a token from what you register here.
  - **Web Crawler** (`/settings/web-crawler`) — tunables for the web-crawl ingestion path.
  - **API Documentation** (`/settings/api-docs`) — static reference for the full JSON API.
  - **Data Model** (`/settings/data-model`) — a zoomable ER diagram plus column-level reference
    for every table, generated from the actual schema.

None of the `/settings/*` pages are reachable without logging in first, and none of them accept
the bearer token — they use the browser session + a CSRF header instead. The bearer-token OAuth2
API (`/oauth/token` and everything under scopes) is a separate, independent auth surface for
non-browser clients; see the next section.

## First Login & Getting an API Token

**Step 1 (log in) is required for everyone.** Step 2 onward — registering an Application and
getting a bearer token — is **optional**, and only needed if something *other than your browser*
needs to call the API:

- **Not needed** if you're just using the app through the browser (`/workspace` to create
  libraries and ingest documents, `/settings` to configure providers). The SPA authenticates with
  your login session cookie, not a bearer token — nothing below this point is required for that.
- **Not needed** for the bundled MCP server either (the one this image exposes for clients like
  Claude Code) — it authenticates to the API automatically using a built-in service-account
  Application created at first boot, with no credential you ever see or configure.
- **Needed** if you want to call the JSON API directly — `curl`/scripts/your own automation — or
  connect a separate external client (e.g. a different app entirely, not the bundled MCP server)
  that talks to this API over HTTP instead of through the browser. Every route outside `/login`
  and `/settings/*` requires a scoped bearer token; there's no unauthenticated or static-API-key
  path into it.

If that's your use case:

1. Open `http://localhost:13102/login` in a browser. Default credentials are `admin` / `admin` —
   you'll be forced to set a new password on first login.
2. Go to **Settings → Applications** to register an OAuth2 application (client id + secret,
   shown once) for the external client that needs to call the API — the client secret is hashed
   at rest and never shown again after registration.
3. Exchange those credentials for a bearer token:
   ```bash
   curl -X POST http://localhost:13102/oauth/token \
     -H "Content-Type: application/json" \
     -d '{"grant_type":"client_credentials","client_id":"...","client_secret":"...","scope":"libraries:read query:execute"}'
   ```
4. Use the returned `access_token` as `Authorization: Bearer <token>` on every API route. Access
   tokens are short-lived (1 hour); request the `offline_access` scope to also receive a
   refresh token.

Available scopes: `libraries:read`, `libraries:write`, `documents:read`, `documents:write`,
`query:execute`, `embedding_settings:read`, `embedding_settings:write`, `search_settings:read`,
`search_settings:write`, `web_crawl_settings:read`, `web_crawl_settings:write`, `offline_access`.

## Configuring an Embedding Provider

Every embedding provider starts **disabled** — you must configure and enable exactly one before
creating libraries or ingesting documents (only one can be enabled at a time; enabling a different
one disables whichever was active). Once any chunks have been embedded, that provider's model and
dimensions become **locked** — you can still edit chunk size, chunk overlap, and the API key, but
changing the model/dimensions or disabling it requires deleting every document first, since
embeddings from different models aren't comparable.

Three providers are supported: **Ollama** (local, no API key), **Voyage** (hosted, needs an API
key), and an **OpenAI-compatible** endpoint (hosted or self-hosted, needs a base URL). All three
are configured the same way, from **Settings → Providers** (`/settings`) — click a provider's
tile to open its settings modal:

| Field | Ollama | Voyage | OpenAI-compatible |
|---|---|---|---|
| API Key | not used | **required** | optional (only if your endpoint enforces one) |
| Base URL | optional — defaults to `http://ollama:11434` | not shown (Voyage's SDK talks to Voyage directly) | **required** |
| Model | e.g. `nomic-embed-text` | e.g. `voyage-3` | e.g. `text-embedding-3-small` |
| Dimensions | e.g. `768` | e.g. `1024` | e.g. `1536` |
| Chunk Size / Overlap | defaults `800` / `100`, editable anytime | same | same |

Fill in the fields, hit **Save**, then flip the toggle on the provider's tile to enable it. The
same operations are plain JSON underneath (`PUT /embedding-settings/<provider>` then
`POST /embedding-settings/<provider>/enable`, both needing `embedding_settings:write`) if you'd
rather script it than click through the UI — see the curl form under Ollama below as a template
for any of the three.

### Ollama (local, no API key)

Ollama runs entirely on your own machine, so it's the option that needs no external account or
API key — good for trying the app out or keeping data fully offline.

1. **Run Ollama and pull an embedding model.** Easiest as its own container on the same Docker
   network as this image, named `ollama` (the default `base_url` above, `http://ollama:11434`,
   matches that container name so you don't need to set a base URL override at all):
   ```yaml
   # add to the docker-compose.yml above
     ollama:
       image: ollama/ollama
       volumes:
         - ollama-data:/root/.ollama
   ```
   ```yaml
   # and to its `volumes:` block
     ollama-data:
   ```
   Then pull the model into it once it's up:
   ```bash
   docker compose exec ollama ollama pull nomic-embed-text
   ```
   Running Ollama on the host instead of in a container also works — set **Base URL** to
   `http://host.docker.internal:11434` (Mac/Windows) instead of relying on the default.

2. In **Settings → Providers**, open the Ollama tile, set **Model** to `nomic-embed-text` and
   **Dimensions** to `768` (that model's output size — a different model needs its own dimension
   count), leave **Base URL** blank unless overriding, and **Save**. Or via curl:
   ```bash
   curl -X PUT http://localhost:13102/embedding-settings/ollama \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"model":"nomic-embed-text","dimensions":768}'
   ```
3. Flip the toggle on the Ollama tile to enable it, or:
   ```bash
   curl -X POST http://localhost:13102/embedding-settings/ollama/enable \
     -H "Authorization: Bearer <token>"
   ```

### Voyage (hosted, API key required)

Get an API key from Voyage AI's dashboard, then in **Settings → Providers** open the Voyage tile,
paste the key into **API Key**, set **Model** to e.g. `voyage-3` and **Dimensions** to `1024`
(matching that model), and **Save** — there's no Base URL field for Voyage. Enable it the same way
as above (toggle, or `POST /embedding-settings/voyage/enable`).

### OpenAI-compatible (hosted or self-hosted, base URL required)

Works with OpenAI itself or any endpoint implementing the same embeddings API shape (e.g. a
self-hosted OpenAI-compatible server). In **Settings → Providers**, open the OpenAI tile, set
**Base URL** (required — e.g. `https://api.openai.com/v1` for OpenAI itself), **API Key** if your
endpoint requires one, **Model** (e.g. `text-embedding-3-small`), and **Dimensions** (e.g.
`1536`), then **Save** and enable it the same way as above.

## Tags

- `sgummalla/knowledge-api:<version>` — e.g. `2.0.1`, matching this repo's `VERSION` file
- `sgummalla/knowledge-api:latest` — always the most recently published version
