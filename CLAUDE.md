# knowledge Project Instructions

This application is called **knowledge** (container/image name: `knowledge`, published to Docker
Hub as `sgummalla/knowledge`). It only runs locally right now (no real production deployment), but
the running `api` container started from that published image is what **knowledge-store** (the
desktop app) and any MCP clients are actively depending on — call it **prod** to keep it
unambiguous from throwaway test/dev-preview containers. There is no repo-local compose file that
builds and runs this container (see Versioning below) — it's always run from the CI-published
`sgummalla/knowledge:latest`/`:<version>` image, the same way `docs/DOCKER_HUB.md` documents for
any other user.

## What this project is

A Flask + Postgres/pgvector RAG backend: create knowledge libraries, ingest documents
(markdown/text/PDF), and retrieve relevant chunks via hybrid (dense + sparse) similarity search.
Structured as hexagonal/clean architecture:
`api/domain` (entities, repository ports as `typing.Protocol`, errors) →
`api/application` (services — one per feature area, no framework imports) →
`api/infrastructure` (SQLAlchemy ORM/repositories, embeddings provider registries, auth
helpers) → `api/presentation` (Flask blueprints/routes, pydantic schemas — JSON only; see item 13,
there is no server-rendered HTML left anywhere in this app — nor any HTML at all, including the
React SPA shell; see item 34). The React SPA (`webui/`) is a **separate deployable from this API**,
run on its own (e.g. `npm run dev`, or its own hosting once built) and talking to this API
cross-origin (`webui/src/api/config.ts`'s `VITE_API_BASE_URL` + this API's CORS allowlist,
`api/presentation/web/cors.py`) — see item 34/35 for the full story, and don't trust item 13's
description of it as bundled/co-served, which predates that change. Bundles an MCP server under
`api/mcp_server/`, exposing three permission-gated tool tiers over streamable-HTTP at
`/<org-slug>/mcp/{search,read,write}`, on the same port as the REST API (not loopback-only — see item
16/23) and secured by the same OAuth2/permission stack as the rest of the API.

## Session history — what's been built (in build order)

1. **Base RAG API** (first commit): libraries CRUD, document ingestion/chunking, pgvector
   similarity search, static `API_KEY` auth, unit + integration (testcontainers) test suite.
2. **Runtime-configurable embeddings** (migration `0002`): a single global `embedding_settings`
   row (provider/model/API key) replaces build-time config, via
   `api/application/embedding_settings_service.py` + `GET/PUT/DELETE /embedding-settings`.
   `GET /embedding-options` exposes the supported provider/model list for UI dropdowns.
3. **Hybrid search** (migration `0003`): dense (pgvector) + sparse (keyword) retrieval fused via
   reciprocal rank fusion (`api/application/rrf.py`), tunable via a global `search_settings` row
   (`api/application/search_settings_service.py`). Originally also had an optional Voyage
   reranking stage; removed entirely in migration `0014` (see item 10) — never mention it as
   still existing.
4. **OAuth2 application auth** (migration `0004`) — the big one:
   - `users` table: single default admin, bootstrapped on first `create_app()` call
     (`api/infrastructure/auth/bootstrap.py`) with username/password `admin`/`admin` and
     `must_change_password=True`, forcing a real first-login password change.
   - `applications` table: named OAuth2 clients (`client_id` = the row's UUID, `client_secret`
     shown once at registration/regeneration, hashed at rest) with an `allowed_scopes` list.
     Registered via the admin's authenticated session (originally the server-rendered dashboard,
     now the React Settings > Applications page — see item 12), **not** via the bearer-token OAuth2
     API — app registration is deliberately never delegable to a scoped access token, since a
     credential able to mint or delete other credentials would be a privilege-escalation vector.
   - `refresh_tokens` table: opaque, SHA-256-hashed, DB-backed, **reusable (not rotated)**.
   - Scopes (`api/constants.py`): `libraries:read`, `libraries:write`, `documents:read`,
     `documents:write`, `query:execute`, `embedding_settings:read`, `embedding_settings:write`,
     `search_settings:read`, `search_settings:write`, `offline_access` (controls whether a
     refresh token is issued — not a resource scope itself).
   - `POST /oauth/token` (`api/presentation/routes/oauth.py`): `client_credentials` and
     `refresh_token` grants, JSON-only, structured `{"error":{"code","message","field"?}}`
     envelope (same shape as every other error response, not bare OAuth2 top-level errors).
   - JWT access tokens (HS256, `SECRET_KEY`, 1hr TTL, stateless verification) — deliberately
     asymmetric with the opaque/DB-backed refresh tokens, since access tokens are checked on
     every request (wants speed) while refresh tokens are rare and must be revocable.
   - `api/auth.py`'s `require_scope(scope)` decorator gates every resource route.
   - Dashboard (now the React Settings > Applications page — item 12): register/delete
     applications, view scopes + (once, on issuance) the client secret in a modal with copy
     buttons, revoke tokens, forced first-login password change, hand-rolled CSRF protection for
     the session-cookie surface (everything else is bearer-token JSON, inherently CSRF-immune).
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
   `api/domain`/templates branding from "rag-api admin" to "Knowledge" in the dashboard UI.
8. **MCP server moved from stdio to streamable-HTTP, with a full OAuth2 `authorization_code` +
   PKCE flow** (migration `0013`), for Claude Code (same machine) to connect over
   `http://127.0.0.1:13103/mcp` instead of being spawned via `docker exec`:
   - `applications.redirect_uris` + `authorization_codes` table (single-use, short-lived,
     hash-only, mirrors `refresh_tokens`' storage pattern).
   - `POST /oauth/register` — unauthenticated RFC 7591 Dynamic Client Registration, capped to
     `DCR_DEFAULT_SCOPES`; deliberately not dashboard-only like normal Application registration,
     since this endpoint (like everything else here) is only ever reachable on localhost.
   - `GET/POST /oauth/authorize` — reuses the dashboard's session login as the consent step
     (originally `api/templates/authorize.html`, a React page since item 13); `/login` now honors
     a `next` param so this doesn't dead-end an unauthenticated visitor.
   - `POST /oauth/token` gained an `authorization_code` branch (PKCE `S256` verification via
     `api/infrastructure/auth/pkce.py`); redirect_uri matching
     (`api/infrastructure/auth/redirect_uri.py`) ignores port for loopback hosts, since a CLI
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
   (`api/infrastructure/auth/bootstrap.py`, called from `create_app()` next to
   `bootstrap_default_admin`) creates a built-in service-account `Application` at a fixed,
   non-secret id (`DEFAULT_MCP_APPLICATION_ID`, `api/constants.py`) the first time the app starts.
   Its secret is never stored, generated randomly, or handed off between processes — both the
   bootstrap step and `mcp_server/client.py` independently derive the same value from `SECRET_KEY`
   via `derive_default_mcp_client_secret` (`api/infrastructure/auth/secrets.py`, HMAC-SHA256), so
   it's unique per deployment without being a literal secret sitting in source control. This
   Application is hidden from the Settings > Applications page's list and its delete/revoke-token
   routes (`api/presentation/routes/auth_ui.py`) — it's internal plumbing, not something an admin
   should be able to accidentally delete. Also bumped gunicorn from its implicit 1-worker default to 3
   (`deploy/entrypoint.sh`) — streamable-http's persistent MCP sessions could otherwise hold the
   single worker's only connection slot and 503 every other request for up to 30s at a time.
10. **Added a Data Model reference page**: zoomable/pannable Mermaid ER diagram plus a
    column-level reference for every table, originally hand-authored once from the live ORM models
    and `migrations/versions/` rather than generated per-request. Originally a Jinja page at
    `/dashboard/schema` with `mermaid.min.js` vendored into `api/static/`; moved to React in item
    13 (`webui/src/pages/DataModelPage.tsx`), now using the `mermaid` npm package instead.
11. **Reranking removed entirely** (migration `0014`) — it had already been unreachable via the
    API since `SUPPORTED_RERANK_MODELS_BY_PROVIDER` was emptied out (see item 3's note): with no
    supported rerank provider, `rerank_enabled` could never be validly turned on, so the feature
    was dead code with no path to re-enable it that didn't also risk a silent runtime failure
    (Voyage reranking reused `embedding_settings.api_key`, with no check that the *embedding*
    provider was actually Voyage — enabling it for, say, an Ollama-embeddings deployment would
    have passed validation and then failed at query time). Rather than gate around that, the
    whole feature was cut: `api/infrastructure/rerank/`, `rerank_choice_validation.py`, the
    `RerankProviderPort`/`RerankProviderRegistry` machinery, `GET /rerank-options`, and the
    `rerank_*` columns on `search_settings` are all gone. `search_settings` now only tunes hybrid
    retrieval (`dense_k`/`sparse_k`/`rrf_k`) — no reranking stage exists anywhere in the pipeline.
    May reconsider later with a cleaner design (e.g. deriving the rerank provider from the active
    embedding provider instead of a separate field) rather than resurrecting this version.
12. **Applications moved from the Jinja dashboard to the React Settings > Applications page**
    (`/settings/applications`, `webui/src/pages/ApplicationsPage.tsx`) — `dashboard.html` and
    `register_application.html` are gone, along with the `GET /dashboard`, `GET
    /dashboard/clients/register` routes. The page is **read-only** by design (list, per-application
    info modal showing client id + scopes, revoke token, delete) — there is deliberately no "Add
    Application" UI; the bundled MCP server and the SPA itself already authenticate via built-in
    service-account Applications with derived, never-stored secrets (item 9), so the only
    remaining use case for registering a *new* Application by hand is an external client like
    knowledge-store, which isn't built yet. The underlying `POST /dashboard/applications`
    registration endpoint (`api/presentation/routes/auth_ui.py`) still exists and is exercised by
    `deploy/smoke_test.py` — it's just not wired to any button. All of `GET/POST
    /dashboard/applications`, `POST /dashboard/applications/<id>/revoke-token`, `POST
    /dashboard/applications/<id>/delete`, `GET /dashboard/scopes` are JSON, kept on the same
    session-cookie + `X-CSRF-Token` header authentication as `/dashboard/token`, deliberately never
    added to the bearer-token OAuth2 API surface (see item 4).
13. **The entire Jinja admin UI was retired — this app now serves zero server-rendered HTML.**
    `api/templates/` and every `render_template()` call are gone; `api/presentation/` is JSON-only
    (routes + pydantic schemas). Everything that was still Jinja after item 12 moved to the React
    SPA (`webui/`), each following the same pattern: the Flask route calls
    `serve_spa_shell(extra_globals=...)` (`api/presentation/web/spa.py`) to inject page-specific
    data as `window.__SOME_GLOBAL__`, and a React page under `/settings/*` (or, for the OAuth
    screen, a new top-level route) renders it client-side:
    - **Web Crawler settings** — was the *entire* contents of the old `/dashboard/configuration`
      page (that page had nothing else on it, so the whole route/template is gone, not just the
      form). Now `webui/src/pages/WebCrawlerPage.tsx` at `/settings/web-crawler`, backed by a new
      scoped JSON API (`GET/PUT /web-crawl-settings`, scopes `web_crawl_settings:read`/`:write` —
      `api/presentation/routes/web_crawl_settings.py`), the same pattern as `search_settings`/
      `embedding_settings` rather than the session+CSRF pattern Applications uses — this data isn't
      credential-shaped, so there's no privilege-escalation reason to keep it off the bearer-token
      API.
    - **API Documentation** — was fully static content (`api_docs.html`, no service calls, no
      Jinja loops); ported near-verbatim into `webui/src/pages/ApiDocsPage.tsx` at
      `/settings/api-docs`. JSON code blocks are template literals (`` {`{...}`} ``) since JSX text
      can't contain a bare `{`.
    - **Data Model** — `webui/src/pages/DataModelPage.tsx` at `/settings/data-model`. The
      zoom/pan/drag toolbar and the ER diagram rendering were rewritten as a dedicated component
      (`webui/src/components/ErDiagram.tsx`) using `mermaid.render()` (returns an SVG string,
      inserted via `dangerouslySetInnerHTML`) rather than `mermaid.run()` (mutates DOM nodes
      in-place, fighting React's reconciliation) — same rationale for using `render()` applies to
      any future mermaid usage in this SPA. `mermaid` is lazy-loaded (`React.lazy` in `App.tsx`):
      it pulls in every diagram-type sub-renderer as separate chunks, and a static import would
      have put that weight in every route's bundle, including `/login`, for a page most sessions
      never visit. The vendored `api/static/mermaid.min.js` is deleted — the npm package replaces
      it, still fully bundled at build time (no runtime CDN dependency, same property the vendored
      file existed for).
    - **OAuth consent screen** (`authorize.html`/`oauth_error.html`) — the one genuinely
      security-sensitive page in this batch, so the server-side validation in
      `api/presentation/routes/oauth.py`'s `authorize()`/`authorize_submit()` (registered
      `redirect_uri` check, PKCE/scope/response_type validation) is **unchanged**; only the
      rendering changed. `GET /oauth/authorize` now calls `serve_spa_shell()` with either
      `OAUTH_AUTHORIZE` (application name + params, once validation passes) or `OAUTH_ERROR`
      (a message, for the two failure modes that must show an error page rather than redirect to
      an unproven `redirect_uri`) injected as a global — `webui/src/pages/AuthorizePage.tsx`
      (a new top-level route, alongside `/login`) picks between the consent form and the error
      view based on which one is present. `POST /oauth/authorize` became JSON: CSRF via the
      `X-CSRF-Token` header instead of a form field (matching `/login`), and instead of an HTTP
      redirect it returns `{"redirect": "..."}` for the client to follow via
      `window.location.href` — same shape `login`/`change-password` already used. The
      `AuthorizeService`/PKCE/redirect_uri validation logic itself was not touched, only how its
      result is delivered to the browser.

    `_sidebar.html`, `base.html`, and the `_inject_embedding_provider_nav_status` context
    processor (the sidebar's per-provider status strip) are deleted outright — nothing renders
    Jinja anymore, so nothing needs them. Both `auth_ui_bp.add_app_template_global(csrf_token)` and
    `oauth_bp`'s equivalent are gone too; `csrf_token()` is still a plain Python function, just
    never registered as a Jinja global now, since `serve_spa_shell()` calls it directly to embed
    `window.__CSRF_TOKEN__`. **If this repo's CLAUDE.md, comments, or memory ever mention a
    "dashboard sidebar," "Jinja admin pages," or a `/dashboard/configuration`,
    `/dashboard/schema`, `/api-docs`, `authorize.html`, or `oauth_error.html` route/template
    outside this item's own history, that reference is stale — none of it exists anymore.**
14. **Renamed `knowledge-api` → `knowledge`** (GitHub repo, the repo directory itself,
    container/image names, and every in-repo reference) — the project had outgrown the "-api"
    suffix: it's a full RAG backend with an MCP server, OAuth2 stack, and React SPA, not just a
    bare API. Image tag `knowledge-api:prod` → `knowledge:prod`, container name `knowledge-api` →
    `knowledge`, test image/container `knowledge-api:testing`/`knowledge-api-test` →
    `knowledge:testing`/`knowledge-test`, compose project names in `deploy/promote-image.sh`/
    `deploy/test-image.sh` updated to match. Docker Hub path
    `docker.io/sgummalla/knowledge-api` → `docker.io/sgummalla/knowledge` (same account, renamed
    repo) in `.github/workflows/publish-image.yml` and `docs/DOCKER_HUB.md`. GitHub repo
    `sgummalla79/knowledge-api` → `sgummalla79/knowledge`. Also renamed the internal
    `_knowledge_api_json_handler` logging marker, the `_ROBOTS_USER_AGENT` outbound crawl
    User-Agent string, and the two secret-derivation labels in
    `api/infrastructure/auth/secrets.py` (safe to change — those secrets are re-derived from
    `SECRET_KEY` on every use, never stored, so bootstrap and client stay in sync automatically).
    `knowledge-store`'s own CLAUDE.md still says "knowledge-api" in places — that's a separate
    repo and wasn't touched by this rename. Same `.venv` stale-shebang quirk noted below applies
    again after the folder itself moved — recreate `.venv` or keep invoking via
    `.venv/bin/python -m <module>` rather than the console scripts directly.
15. **Consolidated the backend into one self-contained `api/` folder.** Renamed `app/` → `api/`
    (every `from app.` import, every `app/…` file-path reference throughout this codebase and this
    file), and moved `migrations/`, `tests/`, `alembic.ini`, `wsgi.py`, `requirements.txt`,
    `requirements-dev.txt`, and `pyproject.toml` from the repo root into `api/` — the backend
    service is now fully self-contained in one directory (`webui/`, `deploy/`, `docs/`, and the
    whole-project `VERSION` file stay where they are). `api/pyproject.toml`'s
    `[tool.pytest.ini_options]` uses `pythonpath = [".."]` (not `["."]`) so `import api.…` still
    resolves with pytest's rootdir now being `api/` itself, not the repo root.
    `deploy/Dockerfile`/`deploy/entrypoint.sh`/`deploy/test-image.sh`/
    `.github/workflows/publish-image.yml` all updated to match (`alembic -c api/alembic.ini`,
    `gunicorn … api.wsgi:app`, `pytest api/tests/`, `pip install -r api/requirements.txt`).
    `.venv` was recreated at `api/.venv` (same "recreate after a folder move" quirk noted above,
    not a simple `mv` — its console-script shebangs embed an absolute path) — every command in this
    file now says `api/.venv/bin/python`, not `.venv/bin/python`. `.env`/`.env.example` moved to
    `deploy/` (a Compose-orchestration concern, not `api/` or `webui/` code — neither reads a
    `.env` file directly); `deploy/promote-image.sh` dropped its `--env-file .env` override since
    Compose's own default lookup (next to `docker-compose.yml`) now already finds it there.
    `.dockerignore` moved to `deploy/Dockerfile.dockerignore` — Docker's own convention: for a
    build invoked with `-f deploy/Dockerfile`, it looks for `<that path>.dockerignore` in the
    context root (the repo root) before falling back to a plain `.dockerignore` there, and
    `deploy/Dockerfile.dockerignore` is itself a valid path within that root (verified empirically,
    including that a real `./deploy/test-image.sh` build still excludes `api/.venv`/`api/tests`
    correctly). Discovered and fixed a real bug in the process: dockerignore patterns are **not**
    gitignore-style — a bare `.venv`/`__pycache__`/`.pytest_cache` pattern only matches at the
    context root, not at any depth, so once those moved under `api/` the old bare patterns silently
    stopped excluding them (confirmed via a throwaway container export showing `api/.venv` actually
    landing in the image). Fixed with explicit `**/` prefixes.

16. **MCP redesigned: merged into the `api` process as three permission-gated tool tiers, then
    moved to `api/mcp_server/`.** Items 8/9 above describe the *first* MCP pass (a separate
    `mcp_server` container/process, 6 hand-picked read-only tools, `list_libraries`/
    `query_library`-style naming, its own `MCP_PORT`/`mcp-entrypoint.sh`) — **none of that exists
    anymore**; if this file, comments, or memory mention a standalone `mcp` compose service,
    `mcp-entrypoint.sh`, `mcp_server/client.py`, `KnowledgeApiTokenVerifier`, or a loopback-only
    `MCP_PORT`, that reference is stale.

    The redesign, in one paragraph: MCP now exposes this app's *actual* API surface, gated by the
    same mechanisms the REST API already has, not a bespoke curated subset. Three separate
    endpoints — `/mcp/rag`, `/mcp/read`, `/mcp/write` — each a fixed, non-overlapping tool set,
    served by the same process/port as the REST API (`api/asgi.py`: Flask wrapped via
    `a2wsgi.WSGIMiddleware`, merged with three native-ASGI `FastMCP` instances into one Starlette
    app — `gunicorn -k uvicorn.workers.UvicornWorker api.asgi:app`, not `api.wsgi:app`). Three
    independent gates, checked in this order by `mcp_server/permissions.py`'s
    `require_tier_permission`: **this application has `mcp_access`** (new `applications.mcp_access`
    boolean, uniform across all three auth methods, migration `0008`) → **this tier is enabled for
    the org** (new `mcp_settings` table, one row per org, three independent booleans, all off by
    default — `api/application/mcp_settings_service.py`, `GET/PUT /mcp-settings`, permissions
    `mcp_settings:read`/`:write`) → **the connecting identity's already-resolved scopes grant this
    specific permission** (reuses `ResolvedCaller.scopes` from `AppAuthService`, the same value
    `require_permission` checks on the HTTP side — no separate profile re-resolution). Tool tiers:
    RAG (`search`, `list_categories`, `get_document`, `get_document_chunks`), object read
    (`list_shelves`, `list_documents`, `list_tags`, `list_embedding_models` — deliberately no org
    member/profile/application visibility, a later "admin capabilities" pass), object write
    (create/rename/delete for documents — inline markdown/text content via `start_ingestion`, not a
    file upload; create/update/delete for categories; create/update/delete +
    add/remove-document for shelves; create/tag/untag for tags — content only, org
    members/profiles/applications are never reachable over MCP regardless of profile, same
    privilege-escalation reasoning item 4 already used for keeping application registration off the
    bearer-token API).

    One real routing bug found and fixed during this pass, worth remembering for any future
    FastMCP-under-Starlette work: nesting a `FastMCP.streamable_http_app()` under an additional
    `Starlette Mount(f"/mcp/{tier}", ...)` breaks its RFC 9728 well-known discovery route (computed
    relative to that sub-app's *own* root, so it ends up double-nested and unreachable at the real
    top-level path). Fixed by setting `streamable_http_path` to the tier's *full* external path
    (e.g. `/mcp/rag`) and merging each server's `.routes` directly into the combined app's
    top-level route list (`api/presentation/web/asgi_bridge.py`) instead of wrapping in `Mount()`.
    Each `FastMCP` server's own lifespan (which starts its `session_manager`) is likewise never
    triggered by Starlette's router unless entered explicitly — the combined app's own `lifespan`
    enters every server's `session_manager.run()` via `contextlib.AsyncExitStack`.

    Also settled during discussion: MCP tiers now share the REST API's port, published the same way
    (not loopback-only like the old separate `mcp` service) — an inherent, accepted consequence of
    one process/one port, not a separate loopback door anymore, offset by the mcp_access + tier +
    permission gate chain above being strictly more restrictive than the old design's bare OAuth2
    check.

    `deploy/`: `mcp`/`mcp-test` compose services and `mcp-entrypoint.sh` deleted;
    `entrypoint.sh`/`docker-compose*.yml` updated as above; `.env.example` drops
    `MCP_PORT`/`MCP_ISSUER_URL`/`MCP_RESOURCE_URL` for a single optional `MCP_BASE_URL`.
    Frontend: `mcp_access` checkbox in `ApplicationCreateModal.tsx` (applies regardless of the
    auth-method radio), new Settings > MCP page (`webui/src/pages/MCPSettingsPage.tsx`, route
    `/org/mcp`) with the three tier toggles.

    **Folder move, same session:** `mcp_server/` (top-level) → `api/mcp_server/` — it was never a
    standalone deployable unit even before this item (no separate entrypoint/container once the
    merge above landed), so it now follows the same "one self-contained `api/` folder" consolidation
    item 15 already did for `app/` → `api/`. Every internal `from mcp_server.X import Y` →
    `from api.mcp_server.X import Y` (including `unittest.mock.patch(...)` target strings in
    `api/mcp_server/tests/`); `api/asgi.py`'s import updated to match. `api/mcp_server/pyproject.toml`
    deleted (redundant — `api/pyproject.toml` already governs everything under `api/`, whose
    `testpaths` gained `"mcp_server/tests"` alongside `"tests"`). `api/mcp_server/tests/integration/
    conftest.py`'s `REPO_ROOT` gained one more `.parent` (one directory deeper now).
    `deploy/Dockerfile.dockerignore`'s bare `mcp_server/tests` entry → `api/mcp_server/tests`;
    `deploy/Dockerfile`'s separate `COPY mcp_server mcp_server` line removed — the existing
    `COPY api api` already brings it in. `deploy/test-image.sh`'s `pytest api/tests/ mcp_server/tests/`
    → `pytest api/tests/ api/mcp_server/tests/`. Full suite (`api/tests/` + `api/mcp_server/tests/`):
    **505 tests passing**.

    `docs/DATA_MODEL.md` still describes an even earlier state (says `mcp_server/` was "removed
    entirely") — that predates this whole item and items 8/9 too; **stale, not yet reconciled with
    any of the OAuth2/profiles/applications/MCP work in this file.**

17. **Self-serve signup collects and validates a chosen org name**, which doubles as the org's
    URL-safe slug — replacing the old auto-generated `"{name}'s org"`. Validated (lowercase/
    digits/hyphens, 3–63 chars, reserved-word blocklist in `api/constants.py`) via
    `api/application/org_name_validation.py`, checked for live availability via
    `GET /check-org-name` as the user types. A collision on submit raises `409
    organization_slug_taken` instead of silently appending a random suffix — that retry-with-
    suffix behavior only ever made sense for an auto-generated name, not one the user
    deliberately typed.

18. **Identity model reworked: `username` replaces `email` as the unique login credential, and an
    identity is now capped to exactly one org for its whole life.** Two previously-conflated
    concepts split apart on `identities`: `username` (new, required, globally unique, must be
    email-*shaped* — validated in `api/application/username_validation.py` — but not verified as
    deliverable) is what `PasswordIdentityVerifier`/`AuthService.login` authenticate against now;
    `email` (kept) is real contact info only, required at signup (validated as email-shaped too,
    via the new `validate_email_format`) but never unique — the `identities.email` column itself
    stays nullable at the schema level since it's still optional for identities created outside
    the validated signup path (invite_member always sets it; the seeded bootstrap admin does not).
    Migration `0013`
    backfills `username = email` for existing rows and drops `email`'s unique constraint — the
    seeded bootstrap admin's `DEFAULT_ADMIN_USERNAME` (`api/constants.py`) changes from `"admin"`
    to `"admin@local"` so new bootstraps satisfy the same format rule (an already-bootstrapped
    admin keeps whatever its backfilled value was — this migration doesn't rewrite existing data
    to the new default).

    Same migration makes `org_members.identity_id` unique — reversing a decision migration 0001's
    module docstring made explicit ("one identity can belong to many orgs and switch between
    them"). That capability was never actually reachable from the UI (no switcher was ever built,
    no "create another org" button existed), and the product direction settled on something
    simpler: which org a username belongs to is decided once, at creation, and never changes.
    Removed as dead weight once the constraint made them structurally impossible to use correctly:
    `POST /orgs/<id>/switch` (`OrgMembershipService.switch_active_org`), `POST /orgs` ("create
    another org" while logged in — `OrgCreateRequest` schema too), and the auto-slug-with-retry
    branch of `create_org_with_owner` (its only caller now is signup, which always supplies an
    exact, pre-validated slug — see item 17). `GET /orgs` itself is unchanged and kept list-shaped
    (now always 0-or-1 entries) since several webui Settings pages already do
    `orgs.data?.find(...)` against it rather than expecting a single object.

    `OrgMembershipService.invite_member` needed one necessary adaptation, not a full redesign
    (that's still open — see "Not yet done" below): it can no longer look up an existing identity
    by email and reuse it, since (a) email isn't unique anymore, so a lookup can match zero, one,
    or several identities, and (b) even a single match is unusable — that identity already belongs
    to a different org and the new constraint forbids adding a second membership. It now always
    creates a brand-new identity per invite, with `username` defaulting to the invited `email` as a
    stopgap.

    Frontend: sign-in relabeled "Email" → "Username"; sign-up's `AuthCard` gained an opt-in `wide`
    prop (every other auth page stays narrow) so it can lay out two columns — Full Name/Org
    Name/Email on the left, Username/Password on the right, submit button spanning both underneath.
    Email is a required field (validated client-side same as everywhere else, server-side via the
    new `validate_email_format`). The `window.__USERNAME__` SPA global
    (`api/presentation/routes/app_shell.py`, consumed by `webui/src/api/shell.ts`'s
    `currentUsername()`) was already named for this — it previously just happened to be backed by
    `identity.email`; only its source changed. Org member listings (`OrgMemberResponse`,
    `webui/src/api/types.ts`'s `OrgMember`) gained `username` and
    made `email` nullable; anywhere a member was previously identified/displayed by email
    (`MembersTable`'s self-detection, `ApplicationsTable`/`ApplicationCreatePage`'s execute-as
    picker) now uses `username` instead, since `email` can no longer be trusted as unique.

19. **`/user/settings` (`webui/src/pages/GeneralSettingsPage.tsx` → `UserSettingsPage.tsx`) turned
    from an org-editing page into a personal account page** — org name/description editing is
    removed entirely, not just hidden: `PATCH /orgs/<org_id>` (`update_org`),
    `OrgMembershipService.update_organization`, `OrganizationRepository.update`, and the
    `OrgUpdateRequest` schema are all gone, since nothing else called them and this app's org name
    is meant to be immutable after signup (see item 17) — **superseded by item 28: org name
    editing was reintroduced, admin-only and password-gated, once description-editing stayed
    removed but the immutability decision itself didn't hold.** The page shows the caller's own Full
    Name/Email/Username/Profile — Profile is editable only for an admin (`profile_is_admin`),
    disabled otherwise, via the existing `PATCH /orgs/<org_id>/members/<identity_id>` (same
    endpoint `MembersTable` already used to change *other* members' profiles). Backed by a new
    `GET /orgs/me` (`orgs.py`) — deliberately gated by `require_org_session` only, no specific
    permission, since `list_members`'s `org_members:read` (needed for the *members list*) isn't
    actually granted to the default Contributor/Viewer profiles, so a non-admin viewing their own
    settings page can't go through `list_members` to find themselves. `useProfiles()`
    (`webui/src/api/queries.ts`) gained an `enabled` param so the page only fetches the org's
    profile list (`profiles:read`, also admin-only) when the viewer is actually an admin —
    otherwise it just displays their current profile name as plain text.

    Full Name, Email, and Username are all editable — but not the same way. Name/email have no
    real security weight, so `PATCH /orgs/me` (→ `AuthService.update_profile`, new
    `IdentityRepository.update_profile`) changes them with no extra confirmation, same as any other
    settings form in this app. Username is different: it's the login credential, so
    `PATCH /orgs/me/username` (→ `AuthService.change_username`, new
    `IdentityRepository.update_username`) requires the caller's *current password* in the request
    body and re-verifies it (`verify_password`) before the change is allowed — deliberately
    inconsistent with `/change-password` (which asks for no current password, since that flow
    exists for a forced first-login change where the caller may not know one yet); a deliberate,
    already-logged-in credential change is a different threat model, closer to "prove it's still
    you" than "you're already past the door." A wrong password returns a plain 401
    (`AuthenticationError`), a taken username the same `409 identity_username_taken` signup already
    uses.

    Also removed the org name from the NavBar account-menu dropdown (previously shown under the
    username) — `currentOrgName()`/`window.__ORG_NAME__` and the `"ORG_NAME"` SPA global
    (`app_shell.py`) are gone too, now genuinely unused rather than just unrendered. Renamed
    throughout the nav ("Org settings" → "User settings" in `NavBar.tsx`'s account menu, "General"
    → "User settings" in `SettingsLayout.tsx`'s sidebar). The route itself was originally left at
    `/org/settings` (a leftover from before this page's purpose changed) and later renamed to
    `/user/settings` to match, once the org-slug-prefixed URL scheme (item 21) made the stale
    naming obvious (`/<org-slug>/org/settings` read as "org" twice).
    Laid out as two columns (Full Name/Email/Profile on the left, the Username change section on
    the right) with the primary Save button moved into the page header — same
    `form="account-form"` attribute-association trick the old `OrgGeneralForm` used to put a submit
    button outside its `<form>` element. The username section keeps its own separate "Update
    username" button in place rather than moving under the header Save, since it's a distinct
    action with its own password-confirmation requirement, not a field saved alongside name/email.

    Profile is **never** self-editable, including for an admin editing their own row — an admin can
    freely change any *other* member's profile between admin/standard, just never their own.
    Enforced in `OrgMembershipService.update_member_profile` (new `acting_identity_id` param,
    compared against the target `identity_id`, raises `ForbiddenError`), not just left as a
    frontend affordance — this is a real authorization rule (prevents both accidental last-admin
    self-lockout and self-escalation), and it closes the same door on both call sites that reach
    this method: `PATCH /orgs/<org_id>/members/<identity_id>` (`MembersTable`'s per-row Select,
    which already disabled the self-row for this reason — now backed by a real check, not just a
    disabled control) and the user-settings page's own Profile field, which now always renders
    read-only.

20. **Confirmed and fixed a real data-integrity gap: pre-existing orgs' `name` didn't match their
    `slug` (and wasn't even slug-shaped) despite item 17/18 making "name is always identical to
    slug" a hard invariant for every *new* org.** The bootstrap default org was the clearest
    offender — its name came from a `DEFAULT_ORGANIZATION_NAME = "Default Organization"` constant
    (spaces, capital letters) paired with `DEFAULT_ORGANIZATION_SLUG = "default"` — but any org
    from the old, now-removed "create another org" flow (free-text name, auto-derived slug) had
    the same mismatch, just less visibly malformed. `DEFAULT_ORGANIZATION_NAME` is deleted;
    `bootstrap_default_organization` now creates the org with `DEFAULT_ORGANIZATION_SLUG` for both
    fields, matching every other org-creation path. Migration `0014` backfills every existing
    mismatched row to `name = slug` (safe and blanket, since slug is always already valid-shaped).
    User settings (item 19) now also shows Org Name (read-only, first field in the left column) —
    surfacing this exact field is what exposed the bug in the first place.

21. **Every post-login route now lives under `/<org-slug>/...`** (e.g. `/acme-corp/browse`,
    `/acme-corp/user/settings`), not the old flat `/browse`. This is purely a URL/routing concern,
    not a new access-control layer — data access was and still is fully enforced by the session +
    Postgres RLS regardless of what's in the URL bar.

    Backend: `app_shell.py` injects a new `ORG_SLUG` global (looked up from `g.org_id`, same as
    `ORG_ID` already was) — always the session's *real* org, never derived from the requested URL
    (`app_shell()` still ignores `subpath` entirely, so `/acme-corp/anything` already matched the
    existing catch-all with zero backend routing changes). `auth_ui.py`'s
    `_consume_post_login_redirect()` — the single choke point sign-in, sign-up, and forced
    change-password all funnel through — now defaults to `/<org-slug>` instead of bare `/` when
    there's no `next=` to honor; the `next=` round-trip itself needed no change, since it already
    just echoes back whatever path was originally requested.

    Frontend: **zero of the ~30 existing `Link`/`navigate` call sites changed.** `App.tsx` reads
    the new `currentOrgSlug()` (`webui/src/api/shell.ts`, mirrors `currentOrgId()`) once and passes
    it as `<BrowserRouter basename={...}>` — React Router prepends the org slug to every absolute
    `to=`/`navigate()` call and strips it before matching routes automatically, so every existing
    route declaration and every existing literal path (`NavBar.tsx`'s `to="/browse"`,
    `SettingsLayout.tsx`'s `LINKS` array, `ItemPage.tsx`'s `` `/item/${id}` ``, ...) kept working
    unchanged. Pre-login pages (sign-in/sign-up/change-password/oauth-authorize) never get an
    `ORG_SLUG` global and render under a `basename`-less mount instead — safe because every
    login/logout boundary is already a full page reload (`window.location.href`, not a client-side
    transition), so both modes never need to coexist in one router instance. `/oauth/authorize`
    specifically stays reachable either way without special-casing, since `oauth.py` never injects
    `ORG_ID`/`ORG_SLUG` regardless of whether the visiting identity happens to be logged in.

    A stale/wrong org slug already in the address bar (old bookmark, manually edited URL, a
    pre-login `next=` built before the identity resolved) self-corrects: `App.tsx` compares the
    URL's first path segment against the authoritative `ORG_SLUG` global before the router even
    mounts, and `window.location.replace()`s to the org's own home (not attempting to preserve
    whatever sub-path was requested — a wrong org's deep link, e.g. an item id, wouldn't resolve to
    anything meaningful in the real org anyway).

    `RESERVED_ORG_SLUGS` needed no changes — it already covers every segment that's still top-level
    under this scheme (`sign-in`, `sign-up`, `change-password`, `oauth`, `static`, `well-known`,
    `health`, ...); app-internal segments like `browse`/`item`/`search` never need reserving since
    they're no longer top-level URL segments at all once nested under `/:orgSlug`. The REST API
    (`/orgs`, `/categories`, `/documents`, ...) is untouched — fetched via JS, never typed into an
    address bar, so it has no reason to carry the org slug too.

    Once the org slug was already establishing org context as the URL's first segment, the
    Settings sidebar's own `org/` prefix on every sub-route became redundant (`/acme-corp/org/shelves`
    read as "org" twice) — dropped from all of them: `org/members` → `members`, `org/profiles(/...)`
    → `profiles(/...)`, `org/shelves` → `shelves`, `org/categories` → `categories`,
    `org/embedding-models` → `embedding-models`, `org/applications(/...)` → `applications(/...)`,
    `org/mcp` → `mcp` (`org/settings` had already become `user/settings` earlier in this same item).
    Same mechanical fix as the `user/settings` rename: route declarations in `App.tsx`,
    `SettingsLayout.tsx`'s `LINKS` array, and every `navigate()`/`Link` call site that referenced
    the old path (`OrgSettingsPage.tsx`, `ProfileFormPage.tsx`, `ProfilesSettingsPage.tsx`,
    `ConnectedApplicationsPage.tsx`, `ApplicationCreatePage.tsx`) — ~30 unrelated `Link`/`navigate`
    calls elsewhere in the app needed no change, same `basename`-does-the-prefixing reasoning as
    above.

22. **Settings > MCP (`webui/src/pages/MCPSettingsPage.tsx`) gained a second column: connection
    instructions for wiring an AI agent up to this org's MCP server**, next to the existing tier
    toggles. Lists all three server URLs (`/mcp/rag`, `/mcp/read`, `/mcp/write` off
    `window.location.origin`, no org-slug prefix needed — MCP resolves the org from the bearer
    token's claims, not the URL) unconditionally, each copyable and tagged Enabled/Not enabled
    against the *saved* tier settings (not unsaved checkbox edits) — the URLs are a fixed part of
    this app's MCP surface, shown regardless of whether a tier happens to be toggled on right now.
    Below the list, a shared note covers both the generic connection shape (Streamable HTTP
    transport, `Authorization: Bearer <token>` header) and the Claude-Code-specific `claude mcp add
    --transport http ... --header "Authorization: Bearer <token>"` form. Links to
    `/user/api-keys` for the personal access token itself (MCP tool calls authenticate
    identically whether the caller is a Connected Application or a personal access token — both
    carry their own `mcp_access` flag, checked in `api/mcp_server/permissions.py`'s
    `require_tier_permission`).

    `docs/DOCKER_HUB.md`'s own "Connecting Claude Code (MCP)" section is a leftover from the
    pre-item-16 standalone MCP server (loopback-only port 13103, browser-consent OAuth flow, no
    token to paste) — **stale**, not reconciled with this page or the current bearer-token design;
    not touched as part of this item.

23. **Every org now has its own real MCP server URL — `/<org-slug>/mcp/<tier>`, not the shared
    bare `/mcp/<tier>`** (item 22's UI initially showed the bare URLs; this makes them real).
    Deliberately did **not** make FastMCP itself org-slug-aware — `mcp_server/server.py`'s
    `streamable_http_path` is fixed and doubles as the RFC 9728 well-known discovery route's own
    base path, and templating or nesting it risks the exact bug class `asgi_bridge.py`'s
    `build_asgi_app` docstring already documents one hard-won fix for (well-known discovery
    computed relative to a sub-app's own root, breaking under an extra layer of nesting).

    Instead, new `api/presentation/web/mcp_org_scoping.py`'s `MCPOrgScopingMiddleware` is a thin,
    pure-ASGI layer (not Starlette's `BaseHTTPMiddleware`, which would buffer/interfere with
    streamable-http's long-lived streaming connections) wrapping the whole combined app whenever
    any MCP servers are mounted (`build_asgi_app` now returns `ASGIApp`, not always literally
    `Starlette`). For a request path shaped like `/<org-slug>/mcp/<tier>`: look up the org by slug
    (404 if none), resolve the bearer token via the same `AppAuthService.authenticate_bearer_token`
    `KnowledgeTokenVerifier` already uses (401 if missing, 403 if it resolves to a *different*
    org), then — only once both checks pass — rewrite the path down to the bare `/mcp/<tier>`
    FastMCP actually serves and forward. The bare path is rejected outright (404) when hit
    directly, so there's exactly one valid URL per tier per org now, not a second one that skips
    the org check. One real DB round trip per MCP request beyond what FastMCP's own verifier
    already does (redundant with it, deliberately — simpler and safer than trying to thread a
    pre-resolved caller through the SDK's fixed `TokenVerifier.verify_token(token: str)` interface,
    which has no hook for passing extra context in).

    `webui/src/pages/MCPSettingsPage.tsx`'s connection instructions now build each tier's URL from
    the *current org's* slug (`useOrgs()`'s `Org.slug`, not derived from the browser's current URL
    — the two happen to agree today since `App.tsx` self-corrects a mismatched URL slug, item 21,
    but this page shouldn't depend on that coincidence holding). Later moved again: each tier's URL
    now sits directly under that tier's own checkbox (not in a separate "Connect an AI agent"
    panel) — the checkbox itself already conveys enabled/disabled, so the per-tier "Enabled/Not
    enabled" badge that panel had was dropped as redundant. "Connect an AI agent" is now just the
    how-to-copy-paste instructions (create a token, transport note, Claude Code CLI example) in a
    plain section below the form, with no URLs of its own. Laid out again once more: "Connect an
    AI agent" moved above the tier-toggle form (read the instructions before the checkboxes/URLs
    they refer to), and Save moved into the page header next to the "MCP" title — same
    `form="mcp-settings-form"` attribute-association trick `UserSettingsPage`'s header Save button
    already uses to sit outside its own `<form>` element.

24. **"API keys" moved from the NavBar avatar dropdown into the Settings sidebar**, and its route
    renamed `/account/api-keys` → `/user/api-keys` (`ApiKeysPage.tsx` itself unchanged) — nested
    under `<Route element={<SettingsLayout />}>` in `App.tsx` now instead of being a sibling route
    outside it, and added to `SettingsLayout.tsx`'s `LINKS` array (right under "User settings",
    since it's the other personal/self-service page in that list — every other entry there is
    org-admin). The avatar dropdown now only has User settings and Sign out.

25. **Settings split into two separate sections — "User settings" (personal) and "Setup"
    (org-admin) — each with its own sidebar and URL prefix, replacing the single combined
    Settings sidebar item 24 described.** `webui/src/components/SettingsLayout.tsx` is deleted;
    `UserSettingsLayout.tsx` (`/user/profile`, `/user/api-keys`) and `SetupLayout.tsx`
    (`/setup/users`, `/setup/profiles(/...)`, `/setup/shelves`, `/setup/categories`,
    `/setup/embedding-models`, `/setup/applications(/...)`, `/setup/mcp`) replace it as two
    parallel nav components in `App.tsx`, each its own `<Route element={...}>` wrapper — same
    mechanical route-rename pattern items 21/24 already used (only route paths + the two new
    layout files changed; no page component's own logic changed). `UserSettingsPage.tsx`'s route
    moves `/user/settings` → `/user/profile` and its heading changes "User settings" → "Profile"
    to match its new sidebar label; `OrgSettingsPage.tsx`'s route moves `/members` → `/setup/users`
    and its heading "Members" → "Users" for the same reason. Every internal `Link`/`navigate()`
    call that pointed at an old bare path (`/profiles(/...)`, `/applications(/...)`) now points at
    the `/setup/`-prefixed one — `OrgSettingsPage.tsx`, `ProfileFormPage.tsx`,
    `ProfilesSettingsPage.tsx`, `ConnectedApplicationsPage.tsx`, `ApplicationCreatePage.tsx`. The
    avatar dropdown (`NavBar.tsx`) now has three items — User settings (→ `/user/profile`), Setup
    (→ `/setup/users`), Sign out — instead of item 24's two. `api/constants.py`'s
    `RESERVED_ORG_SLUGS` gained `"user"` and `"setup"` (the latter newly load-bearing now that
    `/setup/...` is a real top-level segment; `"user"` closes a pre-existing gap — `/user/...` was
    already live since item 21 but had never actually been reserved). No backend routing changes
    beyond that one constants addition: `app_shell.py`'s catch-all already ignores `subpath`
    entirely (see item 21), so it serves any `/<org-slug>/setup/...` or `/<org-slug>/user/...` path
    without needing to know the new segment exists — verified via curl against a fresh dev-preview
    org (`GET` on every new path returns `200`, `check-org-name` correctly rejects `setup`/`user`).
    **If this file, comments, or memory ever mention a single combined `SettingsLayout` component,
    `/user/settings`, `/members`, or a bare (non-`/setup/`-prefixed) `/profiles`, `/shelves`,
    `/categories`, `/embedding-models`, `/applications`, or `/mcp` route, that reference predates
    this item and is stale.**

26. **Browser tab favicon set to the brand icon.** The real serving path, missed on the first
    attempt: `api/presentation/routes/app_shell.py` already registers a dedicated
    `GET /favicon.ico` route serving `api/static/brand-icon.png` — deliberately carved out ahead
    of the `/<path:subpath>` catch-all specifically so a browser's automatic favicon request never
    falls through to that `@login_required` route (which would 302 to `/sign-in?next=/favicon.ico`
    and *stash that as the real post-login redirect target*, hijacking sign-in/sign-up). A first
    attempt added `webui/public/favicon.svg` and pointed `index.html`'s `<link rel="icon">` at
    `/favicon.svg` instead — wrong, because `/favicon.svg` isn't a registered Flask route at all,
    so it falls straight into that same catch-all: unauthenticated, a redirect to sign-in (and the
    exact hijack risk the `/favicon.ico` route exists to avoid); authenticated, the SPA's HTML
    shell, never real SVG bytes. Browsers silently fall back to their automatic `/favicon.ico`
    request when the linked icon fails to load, which is why the tab kept showing the old
    stacked-books `brand-icon.png` no matter how thoroughly the cache was cleared — the new icon
    was simply never reachable, not a caching problem. **Corrected fix:** replaced
    `api/static/brand-icon.png` itself (same 128×128 RGBA PNG format, same file the existing route
    already serves) with the new design — the same book-glyph `<path>` `Logo.tsx` uses for the
    NavBar/AuthCard wordmark, filled `#1e9df1` (the computed sRGB hex of the `--primary` OKLCH
    token in `webui/src/index.css`, identical in both palettes) on a transparent background, no
    background shape — rasterized from a throwaway SVG via macOS `qlmanage -t` (no SVG rasterizer
    installed: checked `rsvg-convert`/`imagemagick`/`inkscape`, none present). A first version
    used a filled rounded-square background behind a white glyph; reverted after feedback that a
    solid-color box read as a background swatch rather than a transparent tab icon, in favor of
    matching the existing `brand-icon.png`'s own transparent-canvas convention, then enlarged to
    fill the canvas edge-to-edge (a hairline 1-unit margin on the 32-unit viewBox, up from the
    initial version's 3-unit margin) after feedback that it read too small. `qlmanage` itself
    doesn't preserve SVG transparency — it flattens to a white-composited PNG — so real alpha was
    recovered afterward in Python by inverting the known compositing math (`out = fg·a +
    white·(1-a)`, solved for `a` per pixel; valid here since the glyph is a single flat fill color,
    no gradients) rather than by chroma-keying, which would fringe the anti-aliased edges.
    `index.html`'s `<link rel="icon">` reverted back to plain `/favicon.ico`; `webui/public/`
    (including the unreachable `favicon.svg`) deleted entirely. Verified end-to-end against the
    dev-preview Flask process (no restart needed — a static file swap, not a code change):
    `GET /favicon.ico` returns `200`, `image/png`, and the new icon.

    **Later made theme-adaptive.** Asked to change the glyph to white, then flagged that a
    white-on-transparent PNG is invisible on a light tab bar (the default in most browsers) — a
    single raster image can't know the tab's background color at all, so no fixed color is
    correct in both cases. Resolved properly this time: `api/static/brand-icon.svg` (new) is the
    same glyph with an embedded `<style>`/`@media (prefers-color-scheme: dark)` block — black fill
    by default, white under a dark preference. This is the *correct* signal to key off for a
    favicon specifically (unlike the `dark:` Tailwind-variant mistake earlier in this same item's
    history): a favicon renders in browser chrome, outside the page's DOM entirely, so it only
    ever has access to the OS/browser-level color scheme, never this app's own `data-theme`
    toggle — there's no disconnect this time because that's genuinely the only signal available at
    that layer. A second Flask route, `GET /favicon.svg` (`app_shell.py`, right below the existing
    `/favicon.ico` one, same login-gated-catch-all carve-out and same reasoning), serves it;
    `index.html` gained `<link rel="icon" type="image/svg+xml" href="/favicon.svg">` ahead of the
    existing `.ico` link, which now carries `sizes="any"` to mark it as the fixed-color fallback
    for browsers without SVG-favicon support — left as the existing blue `brand-icon.png`,
    unchanged, since a fallback that can't adapt is safer picking a color legible in both themes
    than picking either black or white outright. Verified the media query itself (not just
    trusting the CSS) by rendering forced light-only and dark-only variants through macOS
    `qlmanage` — confirmed clean black-on-transparent and white-on-transparent respectively — and
    verified `GET /favicon.svg` serves `200`/`image/svg+xml; charset=utf-8` and never reaches the
    login-gated catch-all. Also caught and fixed a real staleness bug this surfaced:
    `api/presentation/web/spa.py`'s `_DEV_SHELL_TEMPLATE` (a hand-maintained duplicate of
    `webui/index.html`'s `<head>`, used only when `WEBUI_DEV_SERVER` is set — see its own docstring
    on why dev mode can't just read the real file) still had the old single `.ico`-only link, so
    the local dev-preview server never actually reflected any `webui/index.html` favicon change
    made earlier in this same item, even though a real build (`npm run build`) always would have —
    updated to match.

27. **`UserSettingsPage.tsx`'s Username section collapsed into the main Profile form and its own
    Save button removed — one Save, gated by a password-confirmation modal when username is
    actually the field that changed.** Supersedes the two-form/two-button layout item 19
    described: `username` is now just another field in `account-form` (seeded from `me.username`,
    same as `name`/`email`), and the separate "Update username" button/form and its always-visible
    "Current password" field are gone. Clicking the single header Save button
    (`form="account-form"`) checks whether `username` specifically is dirty
    (`username !== me.username`): if not, it submits directly via the existing password-free
    `PATCH /orgs/me`, unchanged from before; if it is, nothing is submitted yet — a new
    `ConfirmUsernameModal` (built on the existing `Modal` + `PasswordField` components, the same
    pattern `InviteMemberModal`/`ShelfFormModal` already use elsewhere in this app) opens instead,
    asking for the current password before anything is written. Confirming the modal calls `PATCH
    /orgs/me` first if name/email were *also* dirty, then `PATCH /orgs/me/username` with the
    password — both endpoints, requirements, and error codes are unchanged, only the frontend
    orchestration is new. Deliberately atomic: cancelling the modal saves nothing at all (not even
    the name/email part), so a changed-username Save is all-or-nothing, and a wrong password just
    re-shows the error inside the modal without losing any typed field. Verified the two API
    contracts this depends on directly via curl against the dev-preview: `PATCH /orgs/me` with no
    `current_password` succeeds; `PATCH /orgs/me/username` succeeds with the right password and
    returns `401 unauthorized`/`"Incorrect password."` with a wrong one.

28. **Org name editing reintroduced on `UserSettingsPage.tsx`** — admin-only, password-gated, and
    forces a full sign-out on success, unlike the plain profile fields. Org name doubles as every
    member's URL slug (item 20's `name == slug` invariant, enforced end-to-end since org creation
    stores `name` and `slug` as the same value — see item 17), so this isn't a display-label edit:
    the input takes the same slug-shaped value (`validate_org_slug` — lowercase/digits/hyphens,
    reserved-word check) signup already validates, not free text. New `PATCH /orgs/<org_id>` route
    (`orgs.py`), gated by `@require_permission("org:write")` — reusing a permission scope that
    already existed in `OBJECT_PERMISSIONS` and was already seeded onto every org's Admin profile
    and labeled "Rename / describe org" in `ProfileFormPage.tsx`'s permission editor, left over
    from before item 19 removed the feature it was written for; no new scope was needed. New
    `OrgMembershipService.change_organization_name(org_id, acting_identity_id, current_password,
    new_name)` re-verifies the acting admin's own password (`verify_password` against their
    `Identity.password_hash`, same primitive `AuthService.change_username` already uses) before
    calling new `OrganizationRepository.update_name` (writes `name` and `slug` together, always;
    `IntegrityError` on a slug collision → `ConflictError`, mirroring `create`'s existing handling
    — port method added to `OrganizationRepositoryPort`).

    Frontend: `UserSettingsPage.tsx`'s "Org name" field goes from always-disabled to
    conditionally-editable (`org.permissions.includes('org:write')`) — disabled with a "Only an
    admin can change the organization name" hint otherwise. A warning banner (new `WarningIcon` in
    `icons.tsx`) sits above the form, unconditionally, stating that changing username (and, for an
    admin, org name) requires the current password and signs the browser out immediately. First
    version used raw Tailwind `yellow-500`/`yellow-700 dark:text-yellow-400` classes instead of a
    design token — wrong, and reported as unreadable in light mode: this app's dark mode is an
    explicit `data-theme="dark"` attribute toggle (`theme.ts`), not
    `prefers-color-scheme`-driven, and `index.css` has no `@custom-variant dark` remapping
    Tailwind's `dark:` prefix to match it (confirmed `dark:` wasn't used anywhere else in this
    codebase before this page) — so `dark:text-yellow-400` only ever tracked the OS-level color
    scheme, completely independent of the app's own toggle, producing the reported light-on-light
    text whenever the two disagreed. Fixed by adding a real `--warning` token to `index.css` (same
    single-oklch-value-in-every-theme-block pattern `--destructive` already uses, plus the
    `@theme inline` mapping so `text-warning`/`border-warning`/`bg-warning` exist as real Tailwind
    utilities) rather than reaching for another one-off raw color — confirmed via a throwaway HTML
    render (`qlmanage -t`, no browser available in this environment) that the resulting amber text
    is legible against both a white and a solid-black background, matching this app's real
    `--background` values in each theme. The username field's own inline hint ("Changing user
    name requires your current password") was also removed as redundant now that the same
    information is already stated once, up front, in the banner. The username and org-name
    confirmation flows were unified into
    one `ConfirmSensitiveChangeModal` (renamed from item 27's `ConfirmUsernameModal`) rather than
    two separate modals, since Save can trigger both at once if an admin edits both fields in the
    same pass — its body text lists whichever of the two actually changed. `handleConfirm`
    deliberately orders its calls **password-gated first, password-free profile patch last**: if
    the password is wrong, the org-name/username call throws immediately and `saveProfile()` (no
    password check at all) never runs, so a rejected confirm leaves *everything* uncommitted,
    including any name/email edit made in the same Save — verified directly via curl against the
    dev-preview (wrong password → org slug, profile name, and session all unchanged; correct
    password → org rename + username change + profile update all land, then `POST /logout`
    confirmed by a subsequent `401`). Every other org member self-corrects to the renamed URL on
    their next request via the existing mechanism (item 21's `ORG_SLUG` self-correction) — only
    the acting admin's own session needs the forced sign-out, since only their browser has the old
    slug baked into `BrowserRouter`'s already-mounted `basename`.

    Test coverage added alongside (591 total now): `api/tests/integration/
    test_org_membership_service.py` gained `_org_with_admin_password` (a variant of the existing
    `_org` helper with a real `hash_password`-backed owner, since `_org`'s plain `"hashed"`
    placeholder can't satisfy a real password check) plus 4 tests (success, wrong password,
    invalid slug, taken slug); `api/tests/unit/test_org_routes.py` gained 3 route-layer tests
    (success, permission-denied, wrong-password-401) following that file's existing
    mock-the-service pattern.

    `account-form` laid out as two columns (`grid grid-cols-1 md:grid-cols-2`, same responsive
    pattern this page used before item 27 collapsed it to one column): left is the two safe,
    unconfirmed fields plus the read-only Profile row (Full name, Email, Profile); right is the
    two password-gated, sign-you-out-on-save fields (Org name, Username) — grouping mirrors the
    safe-vs-sensitive distinction the warning banner above the form already states, not just a
    visual rebalance.

29. **Added an icon-only Home link to `NavBar.tsx`**, right before Browse — new `HomeIcon` in
    `icons.tsx` (same stroke-based style as the other nav icons), `<NavLink to="/" end
    aria-label="Home">` reusing the existing `navLinkClass` active-state styling Browse/Search/
    Dashboard already use. `end` matters here specifically — without it, `to="/"` would match (and
    stay visually "active") on every route, since every path starts with `/`; the brand
    logo/wordmark `NavLink` earlier in this file also points at `/` but never needed `end` since
    its `className` is a static string that ignores `isActive` altogether. Functionally identical
    to clicking the brand logo (same `to="/"` target) — just a second, icon-only way to reach it
    from within the nav row itself, not a new route or behavior. `HomeIcon`'s glyph was redrawn
    once, after feedback that the first pass (two plain strokes for a roofline over a box) read as
    too generic — replaced with a proper house silhouette plus a distinct door cutout (closer to
    Lucide/Feather's stock "home" icon), verified via a throwaway HTML render (`qlmanage -t`, no
    browser available in this environment) in both the inactive and active (`text-primary`) color
    states before landing it.

30. **`NavBar.tsx`'s top-level nav links (Home/Browse/Search/Dashboard) gained a hover
    background**, not just the text-color shift `navLinkClass` already had — asked for without a
    specific color ("think smart"), so reused `hover:bg-secondary` (the same treatment the avatar
    dropdown's own links, and the Settings sidebars, already use) rather than introducing a new
    color choice. A `px-2.5`/`-mx-2.5` pair on each link gives the hover pill room to render
    without nudging the row's existing `gap-7` spacing — the negative margin exactly cancels the
    padding's effect on layout, only the hover background paints outside the text's own box.
    Verified in both themes via a throwaway HTML render (`qlmanage -t`, no browser available in
    this environment) using the real computed hex for `--secondary` in each palette.

31. **Fixed the Contribute nav link (`NavBar.tsx`) always appearing "active."** It had a static
    `className` string with no `isActive` check at all — solid `bg-primary` regardless of which
    page was actually current, unlike every other nav link (`navLinkClass`, item 30), so it always
    looked selected even on Browse/Search/Dashboard. First fix kept it visually distinct as a CTA
    button (solid when inactive, outlined when active) — wrong per explicit correction: Contribute
    isn't meant to be a special-cased button at all, it's meant to be a plain nav link like the
    rest. Now it's just `<NavLink to="/upload" className={navLinkClass}>`, identical in every way
    to Home/Browse/Search/Dashboard — same hover pill, same plain-text look, `text-primary` only
    when `/upload` is actually the current route. All five top-level links now share one styling
    function and behave identically; exactly one is ever highlighted at a time.

32. **Fixed a real, app-wide CSS bug: no text-color utility class ever visually applied to any
    `<a>`/`Link`/`NavLink` element, anywhere in the app** — items 30/31's active/hover nav-link
    colors were the symptom that got noticed, but the root cause was in `webui/src/index.css`
    from the start, affecting every styled link in the SPA (Settings sidebar active-item text,
    `FilterSidebar`, sign-in/sign-up page links, `MCPSettingsPage`'s token link, content cards,
    ...). Cause: `index.css`'s `a { color: inherit; }` reset was bare CSS, not inside a Tailwind
    `@layer` — and CSS Cascade Layers give *any* layered declaration lower priority than *any*
    unlayered one, regardless of specificity. Tailwind v4 emits every utility class (`.text-primary`,
    `.text-accent-foreground`, `.hover:text-primary`, ...) inside its own `@layer utilities`, so
    the bare `a { color: inherit }` always won the color property on every anchor, no matter how
    specific the utility class trying to override it was. Diagnosed with Playwright (installed
    system-wide, not a project dependency — confirmed via `python3 -c "import playwright"`):
    signed into a real dev-preview session, clicked Browse, and inspected the live DOM — the
    correct `text-primary` class *was* present on the active `NavLink`, but `getComputedStyle(...)
    .color` still resolved to `--foreground`, proving a CSS cascade issue rather than a React
    logic bug (the classNames/`isActive` wiring itself was already correct). Fixed by wrapping the
    whole reset block (`*`, `html`/`body`/`#root`, `body`, `a`, `button`, `:focus-visible`) in
    `@layer base` — Tailwind's own convention for exactly this kind of override-able default,
    placing it below `utilities` in priority. Re-verified the same way post-fix: `text-primary`'s
    `color` now resolves to the real `--primary` oklch value, confirmed via screenshot on Browse
    (active, blue) and Dashboard (active, blue) and via hover-state computed color on Search.

33. **Removed the local-build "prod" compose stack — `deploy/docker-compose.yml` and
    `deploy/promote-image.sh` are gone.** They rebuilt `knowledge:prod` from local source and
    restarted it on this machine, duplicating what CI already does: every push to `releases/v4`
    that changes `VERSION` builds and publishes `sgummalla/knowledge:<version>`/`:latest` to Docker
    Hub automatically (`.github/workflows/publish-image.yml`, unchanged by this item). Only two
    local Docker-managed stacks remain, each with its own compose file, ports, and DB, and neither
    building/running the real app image: `deploy/docker-compose.test.yml` (isolated test stack,
    unchanged) and the new `deploy/docker-compose.dev-preview.yml` (just the dev-preview Postgres
    container — `knowledge-dev-preview`, port `15432`, same as before). Going forward, the running
    "prod" container this file's intro paragraph and `docs/DOCKER_HUB.md` describe is always
    started from the published Hub image (`docker run`/a compose file kept *outside* this repo, in
    whatever folder the operator chooses — exactly what `docs/DOCKER_HUB.md`'s Quick Start already
    walks an external user through) — never built from this repo's source on this machine.

    `deploy/dev-preview-up.sh`/`.ps1` and `deploy/dev-preview-down.sh`/`.ps1` (which predate this
    file ever documenting them — see the "Local dev preview" section above, now updated to mention
    them) switched from raw `docker run`/`docker stop`/`docker inspect` calls to
    `docker compose -p knowledge-dev-preview -f deploy/docker-compose.dev-preview.yml
    up -d`/`stop`, project-named the same way `test-image.sh` already named its own stack, to keep
    the two unambiguously separate. One-time migration cost when this landed: the pre-existing
    `knowledge-dev-preview` container wasn't compose-managed, so it had to be removed and
    recreated (fresh throwaway DB — this stack has never held anything but disposable preview
    data, reconfigured each session per the "Local dev preview" section anyway). Neither new
    compose file includes Ollama — dev-preview's Ollama container is still started manually per
    the "Local dev preview" section's existing instructions (unchanged by this item); Ollama
    support is planned for full removal in a later item (see "Not yet done" below), so it
    deliberately wasn't wired into compose now just to be ripped out again shortly. **Superseded by
    item 37: Ollama was removed entirely** — this paragraph is historical, describing the
    deliberate choice at the time, not current state.

    `deploy/test-image.sh` and `.github/workflows/publish-image.yml` had comments referencing the
    now-deleted prod containers/`promote-image.sh` cleaned up; `deploy/smoke_test.py`'s docstring
    similarly no longer says "never run against the prod stack" (there isn't one locally to run
    against) but keeps the underlying warning (don't run it against any shared/long-lived
    instance, since it changes the admin password). **If this file, comments, or memory ever
    mention `deploy/docker-compose.yml`, `deploy/promote-image.sh`, `knowledge:prod` as a local
    image tag, or raw `docker run`/`docker stop` commands for `knowledge-dev-preview`, that
    reference predates this item and is stale.**

34. **The API became a standalone, client-agnostic deployable — this image renders zero HTML,
    including no React SPA shell.** `api/presentation/routes/app_shell.py` and
    `api/presentation/web/spa.py` (`serve_spa_shell()` + the `WEBUI_DEV_SERVER` dev-shell) were
    deleted outright: no more `GET /sign-in`, `/sign-up`, `/change-password`, `/oauth/authorize`
    HTML-rendering routes, no more `window.__CSRF_TOKEN__`/`__USERNAME__`/`__ORG_ID__`/
    `__ORG_SLUG__`/`__OAUTH_AUTHORIZE__`/`__OAUTH_ERROR__` injected into a served page — nothing
    in this API renders HTML at all anymore. Three JSON bootstrap endpoints replace what that
    HTML shell used to embed: `GET /csrf-token`, `GET /session` (401 if not logged in), `GET
    /oauth/authorize-context` (`api/presentation/routes/auth_ui.py`/`oauth.py`). `deploy/Dockerfile`
    dropped its `node:22-slim` webui build stage entirely — this is a pure Python/API image now,
    webui/ is not baked into it. No `/api/` path prefix on any route: API and UI are meant to live
    on separate origins, disambiguated by host, not path. This also shipped a real security pass
    (CSRF required on every cookie-mutation, not just auth routes; explicit
    `SESSION_COOKIE_SAMESITE`/`SECURE`; closed a login timing oracle; a tight per-IP+username
    `POST /sign-in` rate limit; fixed an IDOR on ingestion/crawl job status endpoints) plus
    correlated request/response logging (one structured `method/path/status_code/duration_ms` line
    per request, carrying `request_id`).

    **This item was never recorded when the underlying change landed** — the change itself
    predates this item's own write-up (found and documented only once the gap caused real
    confusion: item 35 below is the fix for the frontend breakage this caused). If this file,
    comments, or memory ever describe `app_shell.py`, `serve_spa_shell()`, `WEBUI_DEV_SERVER`, a
    webui/ build baked into this image, or a browser reading `window.__CSRF_TOKEN__`/
    `__USERNAME__`/`__ORG_ID__`/`__ORG_SLUG__`/`__OAUTH_AUTHORIZE__`/`__OAUTH_ERROR__` as current,
    that reference predates this item and is stale — despite items 12/13/21/26 above still
    describing that machinery as live; those are frozen historical entries, not corrected
    retroactively (this repo's own convention — see item 16's similar note).

35. **Fixed webui/ to actually work against the standalone API from item 34** — until this item,
    the frontend still read the deleted `window.__CSRF_TOKEN__`/etc. globals, so no page (sign-in
    included) could load correctly against a real image; this was only discovered while verifying
    a routine release, not caught by the test suite (webui/ has no such coverage).
    - `webui/src/api/shell.ts`'s `csrfToken()`/`currentUsername()`/`currentOrgId()`/
      `currentOrgSlug()` are unchanged in signature (every existing call site — `NavBar.tsx`,
      `client.ts`'s CSRF header, several Settings pages — needed zero changes) but now read from a
      module-level cache populated by a new `bootstrap()`, which fetches `GET /csrf-token` then
      `GET /session` once. `App.tsx` awaits `bootstrap()` in a `useEffect` before mounting
      `BrowserRouter` (renders `null` until ready) — replaces what used to be synchronously true
      the instant the server-rendered shell loaded.
    - `AuthorizePage.tsx` fetches `GET /oauth/authorize-context` on mount
      (`webui/src/api/oauth.ts`'s new `fetchAuthorizeContext()`) instead of reading
      `window.__OAUTH_AUTHORIZE__`/`__OAUTH_ERROR__`.
    - New `webui/src/api/config.ts` exports `API_BASE_URL` (`import.meta.env.VITE_API_BASE_URL`,
      default `''` for a same-origin/reverse-proxied setup) — every relative fetch path in
      `client.ts`, `auth.ts`, `oauth.ts`, `shell.ts` is now prefixed with it, since a relative path
      no longer reliably resolves to this API's origin (item 34 removed the co-hosted case this
      relied on). `webui/.env.development` sets it to `http://127.0.0.1:13102` (this repo's fixed
      local-dev-preview API port) so `npm run dev` talks to a real local API with zero extra setup;
      override via `VITE_API_BASE_URL` env for anything else. `webui/src/vite-env.d.ts` gained the
      matching `ImportMetaEnv` type.
    - New `api/presentation/web/cors.py`'s `register_cors()`, wired into `create_app()` — every
      resource route is cookie+CSRF authenticated, not bearer-token, so a cross-origin `fetch()`
      with `credentials: 'include'` needs explicit `Access-Control-Allow-Origin` (one
      allowlisted, echoed origin, never `'*'` — required whenever credentials are involved) and
      `Access-Control-Allow-Credentials: true`, plus preflight `OPTIONS` handling. Allowed origins
      come from `WEBUI_ORIGINS` (comma-separated; `api/config.py`'s `config.webui_origins`),
      defaulting to `DEFAULT_WEBUI_ORIGIN` (`api/constants.py`) — the fixed Vite dev-server origin,
      `http://127.0.0.1:5173`, matching `webui/vite.config.ts`'s pinned port. `127.0.0.1` and
      `localhost` are different origins for CORS (and different **sites** for `SameSite` cookie
      purposes, unlike differing only by port, which browsers treat as same-site) — use
      `127.0.0.1` consistently for both the API and webui/ in local dev, not a mix of the two, or
      the session cookie won't be sent cross-origin.
    - Verified end-to-end (not just unit tests, which don't cover webui/ at all): built a real
      image from this branch, ran it alongside a fresh Postgres, pointed a real `npm run dev`
      Vite instance at it via `VITE_API_BASE_URL`, and drove it with Playwright — sign-in,
      CORS preflight, session bootstrap, and the post-login dashboard/document API calls all
      confirmed working end-to-end in a real browser context.
    - `docs/DOCKER_HUB.md`'s Quick Start / "The Admin UI" / "First Login" sections still describe
      the old co-hosted, same-image UI (`http://localhost:13102/login`, no separate webui/ step) —
      **stale as of item 34, not reconciled by this item** — needs its own follow-up once webui/
      has a real hosting story (item 34 called this "a later phase"; no build/deploy path for
      webui/ exists yet beyond `npm run dev` against a real API).

36. **Fixed the sign-up org name field eating hyphens while typing.** `normalizeOrgName()`
    (`webui/src/pages/SignUpPage.tsx`) ran on every keystroke and stripped a trailing hyphen
    immediately — so typing `my-org` character by character never worked, since the hyphen was
    removed the instant it became the last character, before the next character could be typed. A
    trailing hyphen is a normal mid-typing state, not something to eagerly correct;
    `ORG_NAME_PATTERN` already treats it as transiently invalid the same way it treats length < 3,
    and `handleSubmit` now trims leading/trailing hyphens before calling `signUp()` instead of the
    live normalizer doing it on every change. Confirmed with a keystroke-by-keystroke Playwright
    test (typing `"my-test-org"` one character at a time) before and after.

37. **Removed Ollama entirely as a supported embedding provider** — only Voyage and an
    OpenAI-compatible endpoint remain. Requested directly (not a hypothetical "someday" — see item
    34's `docs/DOCKER_HUB.md` note above, which already flagged Ollama's `/settings` walkthrough as
    part of the stale co-hosted-UI docs anyway) ahead of a first real deployment (Hostinger), where
    a self-hosted local-only provider has no place.
    - Deleted `api/infrastructure/embeddings/ollama_provider.py` and
      `api/tests/unit/test_ollama_provider.py` outright. Removed the `"ollama"` entry from every
      shared registry/constants collection it appeared in: `EmbeddingProviderRegistry`'s
      `_PROVIDER_CLASSES`/`_PROVIDER_FACTORIES` (`api/infrastructure/embeddings/registry.py`),
      `EMBEDDING_MODEL_PRESETS`/`EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL`/
      `EMBEDDING_PROVIDER_DISPLAY_NAMES` and the now-unused `DEFAULT_OLLAMA_BASE_URL` constant
      (`api/constants.py`). `GET /embedding-options`'s `default_base_url` field
      (`api/presentation/routes/options.py`) is now unconditionally `None` — no remaining provider
      has an optional-but-defaulted base_url (openai_compatible's is supported *and* required, not
      just defaulted), kept as an explicit field rather than removed in case a future self-hosted
      provider reintroduces one.
    - `embed_provider` is a real Postgres `ENUM`, not app-level-validated free text — edited
      directly in `api/migrations/versions/0001_initial_schema.py` (and the matching
      `api/infrastructure/orm/embedding_model.py` redefinition) rather than added as a new
      migration, since this app has no real deployment anywhere yet (that migration's own module
      docstring) with `provider='ollama'` data to preserve or a schema history to respect — nothing
      to migrate away from, just a value that should never have shipped to the first real
      deployment.
    - Test fixtures across ~11 unit test files and one integration test
      (`test_embedding_dimension_resize.py`) that used `"ollama"` purely as a generic
      no-particular-requirements example provider were repointed at `"openai_compatible"` (with a
      real `base_url`, since that's now required); tests that specifically proved Ollama's
      keyless-and-base-url-less behavior (`test_ollama_default_choice_is_valid_without_api_key`,
      `test_update_ollama_without_api_key_accepted_by_schema`) were deleted outright rather than
      repointed — no remaining provider satisfies "valid with neither an api_key nor a base_url"
      (voyage requires the former, openai_compatible the latter), so there's no equivalent case to
      test. 608 tests passing (down from 624 — accounts for the deleted Ollama-specific test file
      and test functions, not a regression).
    - `webui/src/` needed **zero changes** — `EmbeddingModelsPage.tsx` is fully data-driven off
      `GET /embedding-options`, confirmed by a full-tree grep turning up no Ollama references
      anywhere in `webui/src/` to begin with.
    - Docs: deleted `docs/DOCKER_HUB.md`'s entire `### Ollama` setup subsection (compose YAML with
      an `ollama` service, model-pull instructions, curl examples) and its provider-count/table
      references; updated `docs/DATA_MODEL.md`'s `embed_provider` column description to the
      remaining two values (left its unrelated historical "Voyage→Ollama cutover" mechanism note
      alone — that's describing a real past migration event, not current provider support).
    - **Local dev preview lost its zero-setup, no-external-account embedding option** — Ollama was
      the only provider needing neither a real API key nor a real hosted endpoint. The "Local dev
      preview" section above dropped the Ollama container entirely (table row, first-time-setup
      step, teardown command) and no longer gives a concrete "configure it like this" example,
      since both remaining providers need real credentials/endpoints this file can't supply. If you
      need a genuinely free/local embedding option back for dev-preview specifically, that's new
      work, not a revert — nothing here restores it.
    - `deploy/` scripts needed no changes (dev-preview's Ollama container was only ever started via
      CLAUDE.md's own manual instructions, never wired into any script — see item 33's superseded
      note above); `api/mcp_server/` needed no changes (already fully provider-agnostic).

38. **Renamed the MCP "rag" tool tier to "search"** — route (`/mcp/rag` → `/mcp/search`), DB column
    (`mcp_settings.rag_read_enabled` → `search_read_enabled`), the tier string checked by
    `require_tier_permission`, the tool module (`api/mcp_server/tools/rag.py` →
    `api/mcp_server/tools/search.py`), and the webui Settings > MCP label/example. Prompted by a
    user pointing out that the Settings > MCP page's "RAG (search)" label for the tier implied the
    connection URL should be `/mcp/search`, when it was actually `/mcp/rag` — a fair reading, since
    "RAG" is this whole app's general domain (a RAG backend), so a tier bearing that exact name
    read as ambiguous sitting next to the other two tiers ("read"/"write"), which are both named
    for what they let a caller *do*, not a domain buzzword.
    - `mcp_settings.rag_read_enabled` already had real rows in local dev-preview/verify/test
      Postgres instances (unlike item 37's Ollama enum value, which nothing had ever set) — so
      this got a real migration (`0017_rename_mcp_rag_tier_to_search.py`,
      `ALTER TABLE mcp_settings RENAME COLUMN`), not an in-place edit of the migration that created
      the column (`0008_mcp_access.py`, left untouched).
    - `api/constants.py`'s `MCP_TIERS` (the single (column, URL-segment) source both
      `api/mcp_server/permissions.py` and `GET /mcp-settings`'s `tier_url_segments` derive from)
      changed from `("rag_read_enabled", "rag")` to `("search_read_enabled", "search")` — every
      downstream consumer (permissions tier-lookup, the settings response, webui's per-tier URL
      construction) picked up the rename automatically through that one source, no separate copies
      to chase. The one place that genuinely hardcodes the tier names outside `MCP_TIERS` is
      `api/presentation/web/mcp_org_scoping.py`'s two regexes (`rag|read|write` →
      `search|read|write`) — deliberately not derived from `MCP_TIERS`, since regex alternation
      isn't worth the indirection for three literals that change this rarely.
    - Every "rag" identifier tied to this tier was renamed in lockstep: `api/mcp_server/server.py`'s
      import alias and `_TIERS` dict key, `tools/rag.py`'s own `_TIER` constant (module renamed to
      `tools/search.py`), the domain entity/port/service/repository/route/schema chain
      (`rag_read_enabled` → `search_read_enabled` throughout), test fixtures across
      `api/tests/integration/test_mcp_settings_service.py`,
      `api/mcp_server/tests/unit/test_permissions.py`, `api/mcp_server/tests/integration/
      test_asgi_org_scoping.py` (the middleware regex's own test coverage — updated in lockstep
      with the regex), `conftest.py`'s `enable_tier(..., rag=...)` helper kwarg (→ `search=...`),
      and `test_tools_rag.py` (renamed to `test_tools_search.py`, its `FastMCP(name="test-rag")` and
      one rag-specific test function name updated too). `webui/src/api/types.ts`'s `MCPSettings`
      interface and `MCPSettingsPage.tsx`'s `TIERS` array/form-state/dirty-check all renamed the
      same way; the tile's label changed from `"RAG (search)"` (the ambiguous one) to plain
      `"Search"`, and the `claude mcp add` example's arbitrary client-side server name changed from
      `knowledge-rag` to `knowledge-search` for consistency (that name is cosmetic — any string
      works as the `claude mcp add` argument — but matching the tier avoids a confusing mismatch in
      the copy-pasted example). 608 tests passing throughout (same count as item 37 — a rename, not
      a coverage change).
    - **If this file, comments, or memory ever mention `/mcp/rag`, `rag_read_enabled`, or a `"RAG"`
      tier/tool-tier label as current, that reference predates this item and is stale** — including
      items 16, 22, and 23 above, which still describe the tier as "rag" throughout (frozen
      historical entries, accurately describing what was built at the time — not corrected
      retroactively, this repo's own established convention).

39. **Fixed `GET /oauth/authorize-context`'s not-logged-in redirect pointing at itself.** `next`
    was built from `request.full_path` — this endpoint's own path
    (`/oauth/authorize-context?...`), the JSON bootstrap route `AuthorizePage.tsx` fetches — instead
    of the real consent *page* (`/oauth/authorize`). Signing in via that link would have landed the
    browser on raw JSON instead of the consent screen. Fixed to build `next` from
    `/oauth/authorize` plus the same query string, with a regression test.

    Found via a routine branch-cleanup pass, not fresh work: a local, never-merged branch
    (`releases/v4-webui-phase-b`, authored the night before item 35's session, independently
    redoing the same "fix webui/ for the standalone API" work with a different frontend approach —
    a dev-only Vite proxy instead of item 35's CORS + `VITE_API_BASE_URL`) had already found and
    fixed this exact bug during its own end-to-end testing. That branch's frontend approach diverges
    too far from what's already shipped and verified to merge wholesale without real risk of
    regressing item 35's work, so only this one isolated, self-contained backend fix was
    cherry-picked out of it — the rest of that branch is superseded, not merged.

40. **Built the real Hostinger deployment infrastructure — Kubernetes manifests for the k3s
    cluster already running on that box**, not a Docker Compose stack. `docs/HOSTINGER_DEPLOY.md`
    (the full walkthrough), `deploy/k3s/*.yaml` (namespace, Postgres, API, webui, Traefik
    `Middleware`, `Ingress` × 2, cert-manager `ClusterIssuer`), `deploy/Dockerfile.webui` (+ its own
    `Dockerfile.webui.dockerignore` — Docker's per-Dockerfile-path dockerignore lookup, same
    convention `Dockerfile.dockerignore` already established) and `deploy/nginx.conf`. Real domains:
    `api.sgummallaworks.com/knowledge` (path-prefixed — that domain hosts multiple APIs) and
    `knowledge.sgummallaworks.com` (webui, its own subdomain, no prefix).

    **A Docker Compose + Caddy version of this was built first and fully discarded within the same
    session** before anything was ever applied to a real box — the initial access-model question
    ("SSH access" vs. "prepare files") never surfaced that the actual target was k3s, and by the
    time a diagnostic pass of the box ran (fresh Ubuntu, no Docker, nothing on 80/443), it looked
    like a genuinely empty box rather than a cluster node — the diagnostic script itself never
    checked for `k3s`/`kubectl`. Corrected once the user said outright "my plan is to deploy with
    k3s." A second diagnostic pass then found: k3s already running (fresh install, ~40h uptime),
    Traefik already serving as the built-in Ingress controller (its `LoadBalancer` Service already
    bound to the box's own public IP — explaining why `api.sgummallaworks.com` resolved there with
    nothing answering on 80/443 the first time around), cert-manager installed but with no
    `ClusterIssuer` configured yet, and zero `Ingress` resources — a real blank slate, just one
    layer higher up the stack than the first pass assumed. This also retroactively explained
    `api/config.py`'s older comment about "the Hostinger deployment's Traefik/cert-manager
    termination" — cert-manager is Kubernetes-native tooling; that comment had been describing k3s
    the whole time, a signal worth having caught before building the Compose version at all.

    **Traefik (k3s's bundled Ingress controller), not Caddy**, ended up being the right call after
    all — the earlier "Caddy over Traefik" reasoning (session-internal, from the discarded Compose
    attempt) was specifically about *standing up and hand-configuring* Traefik from scratch for a
    solo operator; under k3s, Traefik is already running, and — the actual deciding factor — each
    future API gets its **own independent** `Middleware`/`Ingress` pair with zero edits to any
    existing resource, which is strictly better than the Compose-era plan's "edit one shared
    `Caddyfile`" story. `04-middleware.yaml`'s `stripPrefix` (namespaced, not derived from any
    single-source-of-truth constant the way item 34's `MCP_TIERS` pattern works — three literal
    tier names change rarely enough that the indirection wasn't judged worth it there either) is
    what removes `/knowledge` before the request ever reaches the API container, which — same as
    the Compose-era design — has no path-prefix awareness at all (item 34: deliberately no `/api/`
    prefix, built assuming origin-based separation).

    `knowledge-api` (`02-api.yaml`) pulls the already-published `sgummalla/knowledge` image
    straight from Docker Hub — no build step on the box for it at all. `knowledge-webui`
    (`03-webui.yaml`) is different: its image bakes in `VITE_API_BASE_URL` at build time (item
    35's design — Vite env vars aren't runtime-configurable) and so is deployment-specific, not a
    reusable published artifact the way the API image is — built once locally on the box
    (`deploy/Dockerfile.webui`, `node:22-slim` → `nginx:1.27-alpine`, plain static-file serving now
    that Traefik owns routing/TLS, no reason for a Caddy-specific image anymore) and loaded directly
    into containerd via `k3s ctr images import` (`docker save` → `k3s ctr images import`), never
    pushed to a registry — `imagePullPolicy: Never` and the fully-qualified
    `docker.io/library/knowledge-webui:local` image reference in the Deployment spec both depend on
    matching exactly what `docker save` embeds for a bare `knowledge-webui:local` tag.

    Both Postgres and the API `Deployment`s use `strategy: { type: Recreate }`, not the Kubernetes
    default `RollingUpdate` — Postgres because its `PersistentVolumeClaim` uses the `local-path`
    StorageClass (node-local storage, not shared; a rolling update briefly running two pods risks
    scheduling the new one onto a different node with an empty volume), the API because — same
    reasoning `deploy/entrypoint.sh`'s own comment already gives for pinning gunicorn to one
    worker — job-status and rate-limit state live in an in-memory dict scoped to one process, so a
    second replica (even briefly, mid-rollout) would silently split that state.

    This surfaced and fixed the same real, previously-undiscovered gap the discarded Compose
    attempt also found: **`webui/vite.config.ts` still described the fully-deleted
    co-hosted-with-Flask architecture** (`base: '/static/workspace/'`, `outDir:
    '../api/static/workspace'`, comments about `serve_spa_shell()`/`WEBUI_DEV_SERVER`) — nobody had
    done a real production build since item 34 deleted that whole serving mechanism. Fixed: `base`
    is always `/` now (webui owns its whole origin, never a sub-path), `outDir` is a plain local
    `webui/dist/`. `.gitignore`'s stale `api/static/workspace/` entry replaced with `webui/dist/`.

    **Known, accepted limitation**: `GET /.well-known/oauth-authorization-server` (RFC 8414) is
    spec-required to live at the domain root, but `api.sgummallaworks.com` hosts multiple APIs each
    wanting their own issuer identity — genuinely incompatible with path-based domain sharing. No
    `Ingress` rule exists for it (404s externally) rather than faking it; nothing currently depends
    on live OAuth auto-discovery (MCP clients authenticate with a pasted personal access token).
    `docs/HOSTINGER_DEPLOY.md` documents this explicitly rather than leaving it a silent surprise.

    Verified locally before handing off (this session has no access to the real Hostinger box —
    "I prepare files, you run them" was the explicit access model): a real `docker build` of
    `Dockerfile.webui` with a real `VITE_API_BASE_URL`, and a real container run of the built image
    confirming both a static asset and the SPA client-route fallback (`/browse` → `200` via
    `try_files`, not a 404) actually serve correctly. Every `deploy/k3s/*.yaml` manifest was
    validated as well-formed YAML with the right `apiVersion`/`kind`/`metadata.name` shape, but
    **not** schema-validated against a live cluster (no kubeconfig for the real box in this
    session's environment) — the Traefik `Middleware` CRD shape and the
    `traefik.ingress.kubernetes.io/router.middlewares` annotation format in particular are worth a
    close read before the first real `kubectl apply`, along with confirming this cluster's real
    `IngressClass` name actually is `traefik` (`kubectl get ingressclass`) before relying on
    `06-cluster-issuer.yaml`'s HTTP01 solver config, which assumes it.

Current test suite: **608 tests passing** (`python -m pytest api/tests/ api/mcp_server/tests/`).

## Not yet done / next steps

- knowledge-store (the desktop app) needs its own separate registered Application (broader scope
  — see that repo's CLAUDE.md) to connect; there's no shared/default credential between clients.
- Invite-flow redesign (planned next, after item 18): `OrgMembershipService.invite_member` always
  creates a new identity per invite today, with `username` defaulting to the invited email as a
  stopgap — a real design still needs to let the inviter choose the invitee's username directly,
  rather than assuming an email-shaped string is also a good username.
- webui/ has no real hosting/deploy story yet (item 34 dropped it from the Docker image; item 35
  only got local dev working via `npm run dev` + `VITE_API_BASE_URL`) — a real build/serve path is
  still needed, and `docs/DOCKER_HUB.md` needs a rewrite once it exists (currently describes the
  old co-hosted single-image setup).
- webui/ has no automated test coverage at all — item 35's frontend/CSRF-bootstrap breakage went
  undetected by the test suite (624 tests, all backend) and was only caught by manual/Playwright
  verification during a routine release.

## Docker testing workflow

There is no locally-built "prod" container in this repo anymore (see the "No local prod
compose" note in Versioning below) — the only two local Docker-managed stacks are the isolated
test stack and the dev-preview database, and they must stay isolated from each other.

All deploy-related files (`Dockerfile`, both compose files, the container entrypoint, and the
dev-preview scripts) live under `deploy/` — everything else in the repo is app code. The
Dockerfile's build *context* is still the repo root (it COPYs `api/`, `VERSION`, etc.), set via
`context: ..` in `docker-compose.test.yml`; only the compose/Dockerfile *files themselves* moved.

`./deploy/test-image.sh` — runs `pytest` (unit tests are mocked, integration tests spin up their
own ephemeral Postgres via testcontainers — neither touches any docker-compose container), then
builds a separate image (`knowledge:testing`) and boots it as `knowledge-test` +
`knowledge-db-test` (`deploy/docker-compose.test.yml`), fully isolated on port 13199 with a
throwaway tmpfs database, under its own compose project (`knowledge-test`) so it's never confused
with the dev-preview stack. Confirms the built image actually boots (migrations run, gunicorn
serves `/health`, and the MCP HTTP server accepts connections on its own loopback-bound port).
Tears the isolated stack down automatically on exit, success or failure.

Once `deploy/test-image.sh` passes and a version-bumped commit lands on `releases/v4`, CI
(`.github/workflows/publish-image.yml`) builds and publishes the real image to Docker Hub
automatically — see Versioning below. There is no local command that builds/runs a "prod" image
on this machine.

## Local dev preview — for interactively clicking around a change, not for CI-style verification

A third option alongside plain `pytest` and `deploy/test-image.sh`: a persistent local Flask dev
server + a throwaway Postgres container, for manually exercising a change in the browser (uploads,
search, Settings pages) without waiting on a Docker image build.
`deploy/dev-preview-up.sh`/`.ps1` and `deploy/dev-preview-down.sh`/`.ps1` automate the entire flow
below (Postgres via `deploy/docker-compose.dev-preview.yml`, migrations, Flask, and webui/'s own
Vite dev server) — run those instead of typing the steps out by hand; the manual commands below are
what they run, kept here for reference and for debugging when a script step fails. Fixed
conventions — reuse these exact values every time rather than picking new ones:

| What | Value |
|---|---|
| Flask dev server | `http://127.0.0.1:15100` |
| Vite dev server (webui/, HMR) | `http://127.0.0.1:5173` |
| Postgres container | `knowledge-dev-preview`, port `15432`, db/user/password all `rag` |
| `SECRET_KEY` | `dev-preview-secret` |
| Flask PID file | `/tmp/workspace-preview.pid` |
| Flask log file | `/tmp/knowledge-dev-preview-flask.log` |
| Vite PID file | `/tmp/workspace-preview-vite.pid` |
| Vite log file | `/tmp/knowledge-dev-preview-vite.log` |

**Quirk:** a `.venv`'s console-script shebangs (`pip`, `alembic`, etc.) embed an absolute path —
after any folder move/rename (this happened for `rag-api` → `knowledge-api`, and again for
`app/` → `api/`, which is why `.venv` now lives at `api/.venv`, not the repo root — see CLAUDE.md's
session history) they'll fail with "bad interpreter" if not recreated. Always invoke via
`api/.venv/bin/python -m <module>` (e.g. `python -m alembic`, `python -m pip`) instead of the
console script directly.

**First-time setup / after an `api/.venv` rebuild:**
```bash
# 1. Throwaway Postgres — via deploy/docker-compose.dev-preview.yml (pgvector/pgvector image is
# required, plain postgres lacks the extension). `dev-preview-up.sh`/`.ps1` run this same command
# for you along with the rest of the steps below.
docker compose -p knowledge-dev-preview -f deploy/docker-compose.dev-preview.yml up -d

# 2. Migrations
DATABASE_URL=postgresql://rag:rag@127.0.0.1:15432/rag SECRET_KEY=dev-preview-secret \
  api/.venv/bin/python -m alembic -c api/alembic.ini upgrade head

# 3. Vite dev server (webui/, HMR) — leave running, tracking its PID. Overrides
# webui/.env.development's VITE_API_BASE_URL (which points at the verify/"prod" API port, 13102 —
# see session history item 35) to this flow's Flask port instead.
cd webui && VITE_API_BASE_URL=http://127.0.0.1:15100 \
  nohup npm run dev > /tmp/knowledge-dev-preview-vite.log 2>&1 &
disown
echo $! > /tmp/workspace-preview-vite.pid
cd ..

# 4. Start Flask, tracking its PID — pure JSON API now (see session history item 34), no HTML/SPA
# serving of any kind, so no WEBUI_DEV_SERVER or equivalent to set here. Its default CORS allowlist
# (DEFAULT_WEBUI_ORIGIN, api/constants.py) already matches Vite's fixed 127.0.0.1:5173 above, so no
# WEBUI_ORIGINS override is needed for this exact port combination either.
DATABASE_URL=postgresql://rag:rag@127.0.0.1:15432/rag SECRET_KEY=dev-preview-secret \
  nohup api/.venv/bin/python -m flask --app api.wsgi run --port 15100 \
  > /tmp/knowledge-dev-preview-flask.log 2>&1 &
disown
echo $! > /tmp/workspace-preview.pid
```
Then open `http://127.0.0.1:5173/sign-in` (Vite serves the actual UI now — Flask's own
`127.0.0.1:15100` answers only JSON, see item 34/35) — `admin@local`/`admin`, forced password
change on first login. To ingest/query anything you'll also need to configure an embedding
provider once (Providers tab) — Voyage (needs a real API key) or an OpenAI-compatible endpoint
(needs a real base URL); neither is a zero-setup local default anymore now that Ollama support has
been removed (see item 36), so there's no single example to give here — use whichever real
provider/credentials you have.

**Day-to-day after that (containers already running):**
- **Backend code change:** Flask's dev server doesn't hot-reload — kill the tracked PID
  (`kill $(cat /tmp/workspace-preview.pid)`, never by port — see the process-safety note below)
  and re-run step 4 above (Postgres/Vite stay up, so only Flask needs restarting).
- **Frontend-only change:** nothing to do — Vite's dev server hot-reloads the browser directly.
  Leave `npm run dev` (step 3) running for the whole session; only restart it if it crashes or the
  webui/ dependency tree changes (e.g. after `npm install`). `npm run build` is no longer part of
  producing the API image (`deploy/Dockerfile` dropped its webui/ build stage — see item 34) and
  webui/ has no real hosting story yet (see "Not yet done" below) — `npm run dev` against a real
  API is the only way to run it today.
- **Don't tear the containers down between checks** — keep this as one stable, persistent preview
  across a session rather than recreating it for every verification pass; the user may be clicking
  around the same URL. If you need a DB for your own throwaway/automated test script, spin up yet
  another separate container/port rather than reusing this shared preview's data.
- **Never kill by port** (e.g. `lsof -ti:15100 | kill`) — on this machine that pattern has taken
  down Docker Desktop itself before. Always kill by the exact tracked PID or `docker rm -f
  <container-name>`.

**Full teardown**, once genuinely done with the preview:
```bash
kill $(cat /tmp/workspace-preview.pid) 2>/dev/null
kill $(cat /tmp/workspace-preview-vite.pid) 2>/dev/null
docker compose -p knowledge-dev-preview -f deploy/docker-compose.dev-preview.yml down
```

## Versioning

The repo root `VERSION` file (plain text, single line, e.g. `3.0.0`) is the single source of truth
for the app's release version, following semver (`MAJOR.MINOR.PATCH`).

**Release history:**
- `releases/v1` — the first release line, starting at `1.0.0`, cut from `master`. **Closed:
  permanently locked, no further changes of any kind.** Kept only for historical reference — do
  not branch off it, commit to it, or cherry-pick from it.
- `releases/v2` — the second release line, cut from `master` at `2.0.0` after merging in the full
  Jinja-to-React migration (`feature/workspace-ui`: retired the server-rendered admin UI entirely,
  moved every page to the React SPA in `webui/`, added the toast notification system). **Closed as
  of the `releases/v3` cutover: permanently locked, no further changes of any kind.** Kept only for
  historical reference — do not branch off it, commit to it, or cherry-pick from it, same as
  `releases/v1`.
- `releases/v3` — the third release line, cut from `master` at `3.0.0`. Diverged early into
  `releases/v3-multi-tenant-data-model`, a long-running rework of the entire data model
  (organizations/identities/org_members, OAuth2, profiles, MCP merged into the api process,
  org-slug routing, and a full `webui/` rebuild on top of it all) that eventually became the whole
  of `releases/v3`'s own content — merged into `releases/v3` at `4.0.0`, tagged `v4.0.0`. **Closed
  as of the `releases/v4` cutover: permanently locked, no further changes of any kind.** Kept only
  for historical reference — do not branch off it, commit to it, or cherry-pick from it, same as
  `releases/v1`/`releases/v2`.
- `releases/v4` — the active release line, cut from `master` at `4.0.0`. This is the current base
  for all work.

**`master` and `releases/v4` are protected — never commit directly to either, from any machine.**
All work (bug fixes and features) happens on a short-lived branch cut from `releases/v4`, then
merged back via the workflow below. `master` only ever receives commits via cherry-pick from
`releases/v4`, never direct commits. If a task would require committing straight to `master` or
`releases/v4`, stop and cut a branch first instead.

**Fix/feature workflow — follow exactly, from any machine:**

1. Branch off `releases/v4` for the work (e.g. `releases/v4-fix-<short-description>`).
2. Make and test the change.
3. Before committing, bump the appropriate number in `VERSION` (`PATCH` for bug fixes, `MINOR` for
   backward-compatible feature additions, `MAJOR` for breaking changes — e.g. `4.0.0` → `4.0.1`)
   and include that bump in the same commit as the change.
4. Push the branch, verify it (see the Docker testing workflow above), then merge into
   `releases/v4`. That push (with the changed `VERSION`) triggers CI
   (`.github/workflows/publish-image.yml`) to build and publish
   `docker.io/sgummalla/knowledge:<version>` + `:latest` automatically — there is no local
   "promote" step.
5. Tag the merge commit on `releases/v4` with `v<version>` (e.g. `v4.0.1`) and push the tag.
6. Cherry-pick the fix/feature commit onto `master` — squashed into one commit if the branch
   accumulated more than one (as `releases/v3-multi-tenant-data-model` did: 22 commits, squashed
   to a single commit on `master` while keeping full history on `releases/v3`/the feature branch
   itself), otherwise cherry-picked as-is. Exclude the branch's own `VERSION` bump if it was a
   separate commit. `master`'s `VERSION` file is independent of `releases/v4`'s and is not kept in
   sync day-to-day — `master` is expected to be ahead in features, so its own version number is
   tracked separately — except at a release-line cutover itself, where the two are deliberately
   realigned (as they were for the `3.0.0` and now `4.0.0` cutovers) so the next release line
   starts from a clean, matching base.
