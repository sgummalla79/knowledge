# knowledge-api Project Instructions

This application is called **knowledge-api** (container/image name: `knowledge-api`, prod image
tag `knowledge-api:prod`). It only runs locally right now (no real production deployment), but the
running `api` container is what **knowledge-store** (the desktop app) and any MCP clients are
actively depending on — call it **prod** to keep it unambiguous from throwaway test containers.

## What this project is

A Flask + Postgres/pgvector RAG backend: create knowledge libraries, ingest documents
(markdown/text/PDF), and retrieve relevant chunks via hybrid (dense + sparse) similarity search.
Structured as hexagonal/clean architecture:
`app/domain` (entities, repository ports as `typing.Protocol`, errors) →
`app/application` (services — one per feature area, no framework imports) →
`app/infrastructure` (SQLAlchemy ORM/repositories, embeddings/rerank provider registries, auth
helpers) → `app/presentation` (Flask blueprints/routes, pydantic schemas, Jinja2 admin dashboard
templates). Bundles a stdio MCP server (`mcp_server/`) exposing `list_libraries`/`query_library`
tools, run via `docker exec` from the same container.

## Session history — what's been built (in build order)

1. **Base RAG API** (first commit): libraries CRUD, document ingestion/chunking, pgvector
   similarity search, static `API_KEY` auth, unit + integration (testcontainers) test suite.
2. **Runtime-configurable embeddings** (migration `0002`): a single global `embedding_settings`
   row (provider/model/API key) replaces build-time config, via
   `app/application/embedding_settings_service.py` + `GET/PUT/DELETE /embedding-settings`.
   `GET /embedding-options` exposes the supported provider/model list for UI dropdowns.
3. **Hybrid search** (migration `0003`): dense (pgvector) + sparse (keyword) retrieval fused via
   reciprocal rank fusion (`app/application/rrf.py`), plus an optional Voyage reranking stage —
   both tunable via a global `search_settings` row (`app/application/search_settings_service.py`).
4. **OAuth2 application auth** (migration `0004`) — the big one:
   - `users` table: single default admin, bootstrapped on first `create_app()` call
     (`app/infrastructure/auth/bootstrap.py`) with username/password `admin`/`admin` and
     `must_change_password=True`, forcing a real first-login password change.
   - `applications` table: named OAuth2 clients (`client_id` = the row's UUID, `client_secret`
     shown once at registration/regeneration, hashed at rest) with an `allowed_scopes` list.
     Registered via the server-rendered admin dashboard (`/login` → `/dashboard`), **not** via any
     JSON API — app registration is deliberately dashboard-only.
   - `refresh_tokens` table: opaque, SHA-256-hashed, DB-backed, **reusable (not rotated)**.
   - Scopes (`app/constants.py`): `libraries:read`, `libraries:write`, `documents:read`,
     `documents:write`, `query:execute`, `embedding_settings:read`, `embedding_settings:write`,
     `search_settings:read`, `search_settings:write`, `offline_access` (controls whether a
     refresh token is issued — not a resource scope itself).
   - `POST /oauth/token` (`app/presentation/routes/oauth.py`): `client_credentials` and
     `refresh_token` grants, JSON-only, structured `{"error":{"code","message","field"?}}`
     envelope (same shape as every other error response, not bare OAuth2 top-level errors).
   - JWT access tokens (HS256, `SECRET_KEY`, 1hr TTL, stateless verification) — deliberately
     asymmetric with the opaque/DB-backed refresh tokens, since access tokens are checked on
     every request (wants speed) while refresh tokens are rare and must be revocable.
   - `app/auth.py`'s `require_scope(scope)` decorator gates every resource route.
   - Dashboard: register/delete applications, view scopes + (once, on issuance) the client secret
     in a popup modal with copy buttons, revoke/regenerate tokens, forced first-login password
     change, hand-rolled CSRF protection for the session-cookie surface (everything else is
     bearer-token JSON, inherently CSRF-immune).
5. **Static `API_KEY` removed entirely** — every route requires a scoped bearer token now; there
   is no unrestricted-access credential anymore. `mcp_server/client.py` is OAuth2-only
   (`MCP_CLIENT_ID`/`MCP_CLIENT_SECRET` env vars, requests `libraries:read query:execute
   offline_access`, refreshes proactively before expiry).
6. **Chunking/embedding-model selection made global** (migration `0005`): `chunk_size`/
   `chunk_overlap`/`embedding_provider`/`embedding_model` moved off the `libraries` table entirely
   and onto the global `embedding_settings` row — there's no per-library override anymore.
   Creating a library now only takes `name`/`description`.
7. **Renamed `rag-api` → `knowledge-api`** (container/image names, and the repo directory itself)
   to match the desktop app's rebrand to "Knowledge Store." Also renamed
   `app/domain`/templates branding from "rag-api admin" to "Knowledge" in the dashboard UI.

Current test suite: **120 tests passing** (`.venv/bin/python -m pytest tests/`).

## Not yet done / next steps

- **MCP isn't actually connected yet** — `.env`'s `MCP_CLIENT_ID`/`MCP_CLIENT_SECRET` are still
  empty. To make the MCP server work: log into `/dashboard`, register an application (e.g. named
  "mcp") with scopes `libraries:read query:execute offline_access`, copy its client_id/secret into
  `.env`, then `docker compose up -d --build api` to pick them up.
- knowledge-store (the desktop app) needs its own separate registered Application (broader scope
  — see that repo's CLAUDE.md) to connect; there's no shared/default credential between clients.

## Docker testing workflow — never test against the prod container

**Rule:** Never run tests, migrations, or manual verification against the `api` / `knowledge-db`
containers defined in `docker-compose.yml` (the prod stack). Rebuilding or restarting them
mid-verification can break a running client or, worse, apply an unverified migration to the real
database.

Instead:

1. `./scripts/test-image.sh` — runs `pytest` (unit tests are mocked, integration tests spin up
   their own ephemeral Postgres via testcontainers — neither touches any docker-compose container),
   then builds a separate image (`knowledge-api:testing`) and boots it as `knowledge-api-test` +
   `knowledge-db-test` (`docker-compose.test.yml`), fully isolated on port 13199 with a throwaway
   tmpfs database, under its own compose project (`knowledge-api-test`) so it's never confused with
   the prod stack. Confirms the built image actually boots (migrations run, gunicorn serves
   `/health`) before it goes anywhere near prod. Tears the isolated stack down automatically on
   exit, success or failure.
2. Only once that passes, run `./scripts/promote-image.sh` — this rebuilds and restarts the prod
   `api` container (`knowledge-api:prod`, via `docker compose up -d --build api`). This is the only
   command allowed to touch the prod container.

Do not shortcut this by running `docker compose up -d --build api` directly as a way to "just check
if it works" — that mutates the prod container immediately, with no isolated verification step
first. If you need to iterate quickly during development, iterate against
`docker-compose.test.yml` (or plain `pytest`), not the prod stack.
