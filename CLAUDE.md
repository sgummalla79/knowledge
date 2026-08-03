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
`app/infrastructure` (SQLAlchemy ORM/repositories, embeddings provider registries, auth
helpers) → `app/presentation` (Flask blueprints/routes, pydantic schemas, Jinja2 admin dashboard
templates). Bundles an MCP server (`mcp_server/`) exposing `list_libraries`/`query_library` tools
over streamable-HTTP, published loopback-only via docker-compose (never reachable off this
machine) and secured by the same OAuth2 stack as the rest of the API — see session history item 8.

## Session history — what's been built (in build order)

1. **Base RAG API** (first commit): libraries CRUD, document ingestion/chunking, pgvector
   similarity search, static `API_KEY` auth, unit + integration (testcontainers) test suite.
2. **Runtime-configurable embeddings** (migration `0002`): a single global `embedding_settings`
   row (provider/model/API key) replaces build-time config, via
   `app/application/embedding_settings_service.py` + `GET/PUT/DELETE /embedding-settings`.
   `GET /embedding-options` exposes the supported provider/model list for UI dropdowns.
3. **Hybrid search** (migration `0003`): dense (pgvector) + sparse (keyword) retrieval fused via
   reciprocal rank fusion (`app/application/rrf.py`), tunable via a global `search_settings` row
   (`app/application/search_settings_service.py`). Originally also had an optional Voyage
   reranking stage; removed entirely in migration `0014` (see item 10) — never mention it as
   still existing.
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
   is no unrestricted-access credential anymore. `mcp_server/client.py` is OAuth2-only (requests
   `libraries:read query:execute offline_access`, refreshes proactively before expiry) — see item 9
   for how it gets its credential.
6. **Chunking/embedding-model selection made global** (migration `0005`): `chunk_size`/
   `chunk_overlap`/`embedding_provider`/`embedding_model` moved off the `libraries` table entirely
   and onto the global `embedding_settings` row — there's no per-library override anymore.
   Creating a library now only takes `name`/`description`.
7. **Renamed `rag-api` → `knowledge-api`** (container/image names, and the repo directory itself)
   to match the desktop app's rebrand to "Knowledge Store." Also renamed
   `app/domain`/templates branding from "rag-api admin" to "Knowledge" in the dashboard UI.
8. **MCP server moved from stdio to streamable-HTTP, with a full OAuth2 `authorization_code` +
   PKCE flow** (migration `0013`), for Claude Code (same machine) to connect over
   `http://127.0.0.1:13103/mcp` instead of being spawned via `docker exec`:
   - `applications.redirect_uris` + `authorization_codes` table (single-use, short-lived,
     hash-only, mirrors `refresh_tokens`' storage pattern).
   - `POST /oauth/register` — unauthenticated RFC 7591 Dynamic Client Registration, capped to
     `DCR_DEFAULT_SCOPES`; deliberately not dashboard-only like normal Application registration,
     since this endpoint (like everything else here) is only ever reachable on localhost.
   - `GET/POST /oauth/authorize` — reuses the dashboard's session login as the consent step
     (`app/templates/authorize.html`); `/login` now honors a `next` param so this doesn't dead-end
     an unauthenticated visitor.
   - `POST /oauth/token` gained an `authorization_code` branch (PKCE `S256` verification via
     `app/infrastructure/auth/pkce.py`); redirect_uri matching
     (`app/infrastructure/auth/redirect_uri.py`) ignores port for loopback hosts, since a CLI
     client's local callback listener uses a different ephemeral port every run (RFC 8252 §7.3).
   - `GET /.well-known/oauth-authorization-server` for client discovery.
   - `mcp_server/server.py` verifies bearer tokens itself (`KnowledgeApiTokenVerifier`, decoding
     the same JWTs `/oauth/token` issues) via the `mcp` SDK's `TokenVerifier` hook — this required
     bumping `mcp` `1.2.0` → `1.27.0` (the old pin had no HTTP transport or auth support at all),
     which cascaded into bumping `pydantic` and `PyJWT` too.
   - Both gunicorn and the MCP HTTP server now start automatically at container boot
     (`deploy/entrypoint.sh`), instead of the MCP server being exec'd on demand per connection.
9. **`mcp_server/client.py`'s outbound credential (MCP process → this app's own REST API) is now
   fully automatic** — no dashboard registration, no `MCP_CLIENT_ID`/`MCP_CLIENT_SECRET` env vars,
   no rebuild-after-editing-`.env` step. `bootstrap_default_mcp_application()`
   (`app/infrastructure/auth/bootstrap.py`, called from `create_app()` next to
   `bootstrap_default_admin`) creates a built-in service-account `Application` at a fixed,
   non-secret id (`DEFAULT_MCP_APPLICATION_ID`, `app/constants.py`) the first time the app starts.
   Its secret is never stored, generated randomly, or handed off between processes — both the
   bootstrap step and `mcp_server/client.py` independently derive the same value from `SECRET_KEY`
   via `derive_default_mcp_client_secret` (`app/infrastructure/auth/secrets.py`, HMAC-SHA256), so
   it's unique per deployment without being a literal secret sitting in source control. This
   Application is hidden from the dashboard's Applications list and its delete/revoke-token routes
   (`app/presentation/routes/auth_ui.py`) — it's internal plumbing, not something an admin should
   be able to accidentally delete. Also bumped gunicorn from its implicit 1-worker default to 3
   (`deploy/entrypoint.sh`) — streamable-http's persistent MCP sessions could otherwise hold the
   single worker's only connection slot and 503 every other request for up to 30s at a time.
10. **Added a Data Model reference page** (`/dashboard/schema`, linked from the sidebar):
    zoomable/pannable Mermaid ER diagram plus a column-level reference for every table, generated
    from the live ORM models and `migrations/versions/` rather than hand-maintained prose.
    `mermaid.min.js` is vendored into `app/static/` (no runtime CDN dependency).
11. **Reranking removed entirely** (migration `0014`) — it had already been unreachable via the
    API since `SUPPORTED_RERANK_MODELS_BY_PROVIDER` was emptied out (see item 3's note): with no
    supported rerank provider, `rerank_enabled` could never be validly turned on, so the feature
    was dead code with no path to re-enable it that didn't also risk a silent runtime failure
    (Voyage reranking reused `embedding_settings.api_key`, with no check that the *embedding*
    provider was actually Voyage — enabling it for, say, an Ollama-embeddings deployment would
    have passed validation and then failed at query time). Rather than gate around that, the
    whole feature was cut: `app/infrastructure/rerank/`, `rerank_choice_validation.py`, the
    `RerankProviderPort`/`RerankProviderRegistry` machinery, `GET /rerank-options`, and the
    `rerank_*` columns on `search_settings` are all gone. `search_settings` now only tunes hybrid
    retrieval (`dense_k`/`sparse_k`/`rrf_k`) — no reranking stage exists anywhere in the pipeline.
    May reconsider later with a cleaner design (e.g. deriving the rerank provider from the active
    embedding provider instead of a separate field) rather than resurrecting this version.

Current test suite: **368 tests passing** (`python -m pytest tests/`).

## Not yet done / next steps

- knowledge-store (the desktop app) needs its own separate registered Application (broader scope
  — see that repo's CLAUDE.md) to connect; there's no shared/default credential between clients.

## Docker testing workflow — never test against the prod container

**Rule:** Never run tests, migrations, or manual verification against the `api` / `knowledge-db`
containers defined in `deploy/docker-compose.yml` (the prod stack). Rebuilding or restarting them
mid-verification can break a running client or, worse, apply an unverified migration to the real
database.

All deploy-related files (`Dockerfile`, both compose files, the container entrypoint, and these
two scripts) live under `deploy/` — everything else in the repo is app code. The Dockerfile's
build *context* is still the repo root (it COPYs `app/`, `mcp_server/`, etc.), set via `context: ..`
in both compose files; only the compose/Dockerfile *files themselves* moved.

Instead:

1. `./deploy/test-image.sh` — runs `pytest` (unit tests are mocked, integration tests spin up
   their own ephemeral Postgres via testcontainers — neither touches any docker-compose container),
   then builds a separate image (`knowledge-api:testing`) and boots it as `knowledge-api-test` +
   `knowledge-db-test` (`deploy/docker-compose.test.yml`), fully isolated on port 13199 with a
   throwaway tmpfs database, under its own compose project (`knowledge-api-test`) so it's never
   confused with the prod stack. Confirms the built image actually boots (migrations run, gunicorn
   serves `/health`, and the MCP HTTP server accepts connections on its own loopback-bound port)
   before it goes anywhere near prod. Tears the isolated stack down automatically on exit, success
   or failure.
2. Only once that passes, run `./deploy/promote-image.sh` — this rebuilds and restarts the prod
   `api` container (`knowledge-api:prod`, via `docker compose -f deploy/docker-compose.yml
   --env-file .env up -d --build api` — the explicit `--env-file` matters here: compose's default
   `.env` lookup follows the first `-f` file's directory, `deploy/`, not the repo root `.env`
   actually lives in). This is the only command allowed to touch the prod container.

Do not shortcut this by running that `docker compose ... up -d --build api` command directly as a
way to "just check if it works" — that mutates the prod container immediately, with no isolated
verification step first. If you need to iterate quickly during development, iterate against
`deploy/docker-compose.test.yml` (or plain `pytest`), not the prod stack.

## Versioning

The repo root `VERSION` file (plain text, single line, e.g. `1.0.0`) is the single source of truth
for the app's release version, following semver (`MAJOR.MINOR.PATCH`). The first release is
`1.0.0`, cut from a long-lived `releases/v1` branch (branched off `master`).

**Bug fix workflow — follow exactly, from any machine:**

1. Branch off `releases/v1` for the fix (e.g. `releases/v1-fix-<short-description>`).
2. Make and test the fix.
3. Before committing the fix, bump the `PATCH` number in `VERSION` (e.g. `1.0.0` → `1.0.1`) and
   include that bump in the same commit as the fix.
4. Push the fix branch, verify it (see the Docker testing workflow above — never test against the
   prod container), then merge into `releases/v1`.
5. Tag the merge commit on `releases/v1` with `v<version>` (e.g. `v1.0.1`) and push the tag.
6. Cherry-pick the fix commit only (not the `VERSION` bump) onto `master`. `master`'s `VERSION`
   file is independent of `releases/v1`'s and is not kept in sync — `master` is expected to be
   ahead in features, so its own version number is tracked separately whenever it cuts its own
   release branch.

Patch bumps are for bug fixes only. Reserve minor bumps for backward-compatible feature additions
and major bumps for breaking changes — neither is covered by this workflow yet.
