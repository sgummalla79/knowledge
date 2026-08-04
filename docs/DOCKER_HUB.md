# sgummalla/knowledge — Docker Hub Overview

This file is the source of truth for the **Overview** tab on
[hub.docker.com/r/sgummalla/knowledge](https://hub.docker.com/r/sgummalla/knowledge).
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

This section assumes **no prior experience** with Docker or the command line. Grey boxes below are
commands: type or paste them into a **terminal** (macOS) or **PowerShell** (Windows) window — a
text-based way to instruct your computer — then press **Enter/Return**. Multi-line blocks (Steps 2
and 3) can be pasted all at once; just press Enter once at the end. Don't skip steps; each depends
on the one before it.

Two files are involved, and **both filenames matter exactly as written** — Docker looks for these
specific names in the folder you run it from:

- **`docker-compose.yml`** — describes what to run. Must be named exactly that, lowercase — not
  `docker-compose.yaml.txt`, not `Docker-Compose.yml`.
- **`.env`** — holds two private, randomly-generated passwords. Must be named exactly `.env`
  (nothing before the dot), in the **same folder** as `docker-compose.yml`.

You won't hand-type either — Steps 2 and 3 give you a command that creates each one for you, named
correctly, automatically.

### 0. Install Docker Desktop

Everything here runs inside **Docker**, a free program that runs apps in self-contained "containers"
so you don't install any of this app's dependencies yourself.

1. Download **Docker Desktop** from Docker's website for your OS (Mac or Windows) and install it
   like any other application.
2. **Windows only:** the installer may prompt to enable **WSL2** — accept it, it's required. Restart
   if asked, then continue the install.
3. Open **Docker Desktop** (Applications folder on Mac, Start menu on Windows) and leave it running
   — wait for it to show a "running" status, which can take a minute the first time. **It must stay
   running in the background** for any command below to work; minimize it, don't quit it.

### 1. Open a terminal and create a project folder

**macOS:** Press `Cmd + Space`, type `Terminal`, press Enter. Then paste and run:
```bash
mkdir -p ~/knowledge && cd ~/knowledge
```

**Windows:** Click Start, type `PowerShell`, open **Windows PowerShell** (or **Terminal**). Then
paste and run:
```powershell
mkdir C:\knowledge; cd C:\knowledge
```

This creates a `knowledge` folder and moves you "into" it. Keep this window open — every
command below is typed into the same window and expects to run from inside this folder.

### 2. Create the compose file (`docker-compose.yml`)

Copy the **entire block below** (first and last line included) for your OS, paste into the same
terminal window, press Enter. This creates a correctly-named file for you — nothing to save by
hand, no risk of a filename typo.

**macOS:**
```bash
cat > docker-compose.yml <<'EOF'
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
    image: sgummalla/knowledge:latest
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
EOF
```

**Windows:** (same idea — paste this whole block into the PowerShell window from Step 1)
```powershell
@'
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
    image: sgummalla/knowledge:latest
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
'@ | Out-File -Encoding utf8 docker-compose.yml
```

No output after pressing Enter means it worked. Double check with `dir` (Windows) or `ls` (macOS)
— you should see `docker-compose.yml` listed.

**Prefer a text editor over the terminal?** Paste the YAML (just the part between the marker
lines, not the markers themselves) and save it — but watch for two common mistakes: **Notepad**
silently adds `.txt` unless you set "Save as type" to **All Files** and type the full name; **macOS
TextEdit** saves rich text (`.rtf`) by default, which breaks the file — use **Format → Make Plain
Text** first.

### 3. Create the `.env` file with your secrets

This holds two private values: a database password and a `SECRET_KEY` used to keep logins secure.
Don't make these up yourself — the commands below generate long random values for you.

**macOS:** paste this into the same terminal window and press Enter:
```bash
cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
EOF
```

**Windows:** paste this into the same PowerShell window and press Enter:
```powershell
@"
POSTGRES_PASSWORD=$([System.Guid]::NewGuid().ToString("N"))
SECRET_KEY=$([System.Guid]::NewGuid().ToString("N") + [System.Guid]::NewGuid().ToString("N"))
"@ | Out-File -Encoding utf8 .env
```

No output means it worked. This file never needs to be opened again. Notes: a filename that's
*only* a dot plus extension (`.env`) is unusual but valid on both OSes; on **macOS**, dot-files are
hidden from Finder by default (not from the terminal) — expected, not a bug. **Never share or
upload this file anywhere** — it holds the credentials to your own instance.

### 4. Start the application

Still in the same window, inside the `knowledge` folder, run:
```bash
docker compose up -d
```
This downloads the two pieces of software this app needs and starts them in the background
(`-d` = "detached" — they keep running after you close this window). First run downloads
everything from the internet, so it can take a couple of minutes with text scrolling by — that's
normal.

### 5. Check that it worked

```bash
docker compose ps
```
You should see two rows, `knowledge-db` and `api`, both `running`/`healthy`. If instead you see
`Exit` or `unhealthy`, see **Troubleshooting** below.

Once healthy, open a browser to `http://localhost:13102/health` — a `200`/small text response (not
an error page) confirms it's up. Then go to `http://localhost:13102/login` — see **First Login**
below.

### Troubleshooting

- **"docker: command not found" / "'docker' is not recognized" / "Cannot connect to the Docker
  daemon"** — Docker Desktop isn't open, or hasn't finished starting (Step 0). Wait for it, then
  retry.
- **"port is already allocated"** — something's already using port `13102`/`13103` (maybe a
  previous run of this guide). Run `docker compose down`, then `docker compose up -d` again.
- **`api` shows `Exit` or keeps restarting** — run `docker compose logs api`; usually `.env` is
  missing or misnamed (Step 3 — must be exactly `.env`, same folder as `docker-compose.yml`).
- **Nothing loads at `/health`** — confirm both rows in `docker compose ps` are running first; if
  so, check for a VPN/firewall/antivirus blocking local connections.
- **To stop:** `docker compose down` (data is kept, `up -d` later resumes where you left off). To
  also erase all data: `docker compose down -v`.

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
- **Not needed** for the bundled MCP server either — see **Connecting Claude Code (MCP)** below.
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

1. **Run Ollama as its own container on the same Docker network as this image**, named `ollama`
   (matches the default `base_url`, `http://ollama:11434`, so no override needed). Don't hand-edit
   your existing `docker-compose.yml` — YAML is indentation-sensitive and easy to break by hand.
   Replace it entirely with this version instead (same file as Quick Start Step 2, with `ollama`
   added):
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
       image: sgummalla/knowledge:latest
       depends_on:
         knowledge-db:
           condition: service_healthy
       environment:
         DATABASE_URL: postgresql://rag:${POSTGRES_PASSWORD}@knowledge-db:5432/rag
         SECRET_KEY: ${SECRET_KEY}
       ports:
         - "13102:13102"
         - "127.0.0.1:13103:13103"

     ollama:
       image: ollama/ollama
       volumes:
         - ollama-data:/root/.ollama

   volumes:
     knowledge-db-data:
     ollama-data:
   ```
   Same paste method as Quick Start Step 2, same folder: on **macOS**, type `cat > docker-compose.yml <<'EOF'`,
   press Enter, paste the YAML above, then a line with just `EOF`. On **Windows**, type `@'`, press
   Enter, paste the YAML above, then a line with `'@ | Out-File -Encoding utf8 docker-compose.yml`.

   **Rewriting the file doesn't restart anything by itself** — apply it the same way as Quick Start
   Step 4:
   ```bash
   docker compose up -d
   ```
   This is the step that actually creates and starts the new `ollama` container — skipping it is
   why you'd see `service "ollama" is not running` if you try the next command too soon. Confirm
   with `docker compose ps` (a third row, `ollama`, `running`), then pull the model:
   ```bash
   docker compose exec ollama ollama pull nomic-embed-text
   ```
   This downloads the actual model weights (a few hundred MB), so it takes a minute. Still failing?
   Check `docker compose logs ollama`, and confirm you're in the same folder as your
   `docker-compose.yml`.

   Running Ollama on the host instead of in a container also works — set **Base URL** to
   `http://host.docker.internal:11434` instead of relying on the default.

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

- `sgummalla/knowledge:<version>` — e.g. `2.0.1`, matching this repo's `VERSION` file
- `sgummalla/knowledge:latest` — always the most recently published version

## Connecting Claude Code (MCP)

This image bundles an MCP (Model Context Protocol) server exposing `list_libraries` and
`query_library` tools, so Claude Code — running on the same machine as the Docker host — can
search your libraries directly. It's published loopback-only (`localhost:13103`, or
`$MCP_HTTP_PORT`) and authenticates itself to the API automatically; there's no client id, secret,
or token for you to create or paste anywhere.

1. Register the server with Claude Code (run once, from any directory). By default this only
   registers it for the current project (`local` scope, private to you); add `-s user` to make it
   available globally, in every project you open on this machine:
   ```bash
   claude mcp add --transport http knowledge http://localhost:13103/mcp
   ```
   Globally, for every project:
   ```bash
   claude mcp add --transport http -s user knowledge http://localhost:13103/mcp
   ```
2. The first time Claude Code calls a tool, it opens your browser to this instance's login/consent
   screen. Log in (`admin` / your changed password) and approve access. Claude Code stores the
   resulting token and refreshes it automatically — you won't be prompted again unless you revoke
   it.
3. Confirm it connected:
   ```bash
   claude mcp list
   ```
   `knowledge` should show as connected. Try asking Claude Code something like "what libraries
   do I have in knowledge?".

Notes:
- Only reachable from the same machine the Docker host runs on — this won't work if Claude Code
  runs on a different machine than Docker itself.
- Running Claude Code inside its own container (e.g. a devcontainer)? Point the URL at
  `host.docker.internal:13103` instead of `localhost`, and confirm the MCP port is actually
  published to the host (see **Ports & Volumes** above).
- To remove it later: `claude mcp remove knowledge`.
