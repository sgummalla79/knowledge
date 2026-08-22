# knowledge Project Instructions

This application is called **knowledge** (container/image name: `knowledge`, prod image
tag `knowledge:prod`). It only runs locally right now (no real production deployment), but the
running `api` container is what **knowledge-store** (the desktop app) and any MCP clients are
actively depending on — call it **prod** to keep it unambiguous from throwaway test containers.

## What this project is

A Flask + Postgres/pgvector RAG backend: create knowledge libraries, ingest documents
(markdown/text/PDF), and retrieve relevant chunks via hybrid (dense + sparse) similarity search.
Structured as hexagonal/clean architecture:
`api/domain` (entities, repository ports as `typing.Protocol`, errors) →
`api/application` (services — one per feature area, no framework imports) →
`api/infrastructure` (SQLAlchemy ORM/repositories, embeddings provider registries, auth
helpers) → `api/presentation` (Flask blueprints/routes, pydantic schemas — JSON only; see item 13,
there is no server-rendered HTML left anywhere in this app). The React SPA (`webui/`, built into
`api/static/workspace/`) is the only UI — see item 13 for how it's served. Bundles an MCP server
(`mcp_server/`) exposing `list_libraries`/`query_library` tools over streamable-HTTP, published
loopback-only via docker-compose (never reachable off this machine) and secured by the same OAuth2
stack as the rest of the API — see session history item 8.

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
    is meant to be immutable after signup (see item 17). The page shows the caller's own Full
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

Current test suite: **584 tests passing** (`python -m pytest api/tests/ api/mcp_server/tests/`).

## Not yet done / next steps

- knowledge-store (the desktop app) needs its own separate registered Application (broader scope
  — see that repo's CLAUDE.md) to connect; there's no shared/default credential between clients.
- Invite-flow redesign (planned next, after item 18): `OrgMembershipService.invite_member` always
  creates a new identity per invite today, with `username` defaulting to the invited email as a
  stopgap — a real design still needs to let the inviter choose the invitee's username directly,
  rather than assuming an email-shaped string is also a good username.

## Docker testing workflow — never test against the prod container

**Rule:** Never run tests, migrations, or manual verification against the `api` / `knowledge-db`
containers defined in `deploy/docker-compose.yml` (the prod stack). Rebuilding or restarting them
mid-verification can break a running client or, worse, apply an unverified migration to the real
database.

All deploy-related files (`Dockerfile`, both compose files, the container entrypoint, and these
two scripts) live under `deploy/` — everything else in the repo is app code. The Dockerfile's
build *context* is still the repo root (it COPYs `api/`, `VERSION`, etc.), set via `context: ..`
in both compose files; only the compose/Dockerfile *files themselves* moved.

Instead:

1. `./deploy/test-image.sh` — runs `pytest` (unit tests are mocked, integration tests spin up
   their own ephemeral Postgres via testcontainers — neither touches any docker-compose container),
   then builds a separate image (`knowledge:testing`) and boots it as `knowledge-test` +
   `knowledge-db-test` (`deploy/docker-compose.test.yml`), fully isolated on port 13199 with a
   throwaway tmpfs database, under its own compose project (`knowledge-test`) so it's never
   confused with the prod stack. Confirms the built image actually boots (migrations run, gunicorn
   serves `/health`, and the MCP HTTP server accepts connections on its own loopback-bound port)
   before it goes anywhere near prod. Tears the isolated stack down automatically on exit, success
   or failure.
2. Only once that passes, run `./deploy/promote-image.sh` — this rebuilds and restarts the prod
   `api` container (`knowledge:prod`, via `docker compose -f deploy/docker-compose.yml up -d
   --build api`; no `--env-file` flag needed — `.env` lives in `deploy/`, right next to
   `docker-compose.yml`, which is exactly where compose looks for it by default). This is the only
   command allowed to touch the prod container.

Do not shortcut this by running that `docker compose ... up -d --build api` command directly as a
way to "just check if it works" — that mutates the prod container immediately, with no isolated
verification step first. If you need to iterate quickly during development, iterate against
`deploy/docker-compose.test.yml` (or plain `pytest`), not the prod stack.

## Local dev preview — for interactively clicking around a change, not for CI-style verification

A third option alongside plain `pytest` and `deploy/test-image.sh`: a persistent local Flask dev
server + throwaway Postgres/Ollama containers, for manually exercising a change in the browser
(uploads, search, Settings pages) without touching the prod stack or waiting on a Docker image
build. Fixed conventions — reuse these exact values every time rather than picking new ones:

| What | Value |
|---|---|
| Flask dev server | `http://127.0.0.1:15100` |
| Vite dev server (webui/, HMR) | `http://127.0.0.1:5173` |
| Postgres container | `knowledge-dev-preview`, port `15432`, db/user/password all `rag` |
| Ollama container | `knowledge-dev-preview-ollama`, port `11500` |
| `SECRET_KEY` | `dev-preview-secret` |
| Flask PID file | `/tmp/workspace-preview.pid` |
| Flask log file | `/tmp/knowledge-dev-preview-flask.log` |
| Vite PID file | `/tmp/workspace-preview-vite.pid` |
| Vite log file | `/tmp/knowledge-dev-preview-vite.log` |

**Why a separate throwaway Ollama container, not prod's:** the prod stack's `ollama` container
(started outside `deploy/docker-compose.yml` historically — check `docker ps` for
`knowledge-ollama-1`) only publishes port 11434 *inside* the compose network (`ollama:11434`),
not to the host, so a bare host-side Flask process can't reach it — and recreating that container
to add a port mapping risks disrupting whatever's currently using it. Spinning up a second,
independent Ollama container costs one quick model pull (`nomic-embed-text` is ~274MB) and keeps
this preview fully isolated from prod, same rationale as the throwaway Postgres.

**Quirk:** a `.venv`'s console-script shebangs (`pip`, `alembic`, etc.) embed an absolute path —
after any folder move/rename (this happened for `rag-api` → `knowledge-api`, and again for
`app/` → `api/`, which is why `.venv` now lives at `api/.venv`, not the repo root — see CLAUDE.md's
session history) they'll fail with "bad interpreter" if not recreated. Always invoke via
`api/.venv/bin/python -m <module>` (e.g. `python -m alembic`, `python -m pip`) instead of the
console script directly.

**First-time setup / after an `api/.venv` rebuild:**
```bash
# 1. Throwaway Postgres — pgvector/pgvector image is required (plain postgres lacks the extension)
docker run -d --name knowledge-dev-preview -p 15432:5432 \
  -e POSTGRES_DB=rag -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag \
  pgvector/pgvector:pg16

# 2. Throwaway Ollama
docker run -d --name knowledge-dev-preview-ollama -p 11500:11434 \
  -v knowledge-dev-preview-ollama-data:/root/.ollama ollama/ollama
docker exec knowledge-dev-preview-ollama ollama pull nomic-embed-text

# 3. Migrations
DATABASE_URL=postgresql://rag:rag@127.0.0.1:15432/rag SECRET_KEY=dev-preview-secret \
  api/.venv/bin/python -m alembic -c api/alembic.ini upgrade head

# 4. Vite dev server (webui/, HMR) — leave running, tracking its PID
cd webui && nohup npm run dev > /tmp/knowledge-dev-preview-vite.log 2>&1 &
disown
echo $! > /tmp/workspace-preview-vite.pid
cd ..

# 5. Start Flask, tracking its PID — WEBUI_DEV_SERVER points serve_spa_shell() (api/presentation/
# web/spa.py) at the Vite dev server above instead of the built webui/ bundle
DATABASE_URL=postgresql://rag:rag@127.0.0.1:15432/rag SECRET_KEY=dev-preview-secret \
  WEBUI_DEV_SERVER=http://127.0.0.1:5173 \
  nohup api/.venv/bin/python -m flask --app api.wsgi run --port 15100 \
  > /tmp/knowledge-dev-preview-flask.log 2>&1 &
disown
echo $! > /tmp/workspace-preview.pid
```
Then open `http://127.0.0.1:15100/login` — `admin@local`/`admin`, forced password change on first login
— and configure the embedding provider once at `http://127.0.0.1:15100/settings` (Providers tab,
the default landing page): model `nomic-embed-text`, base URL `http://127.0.0.1:11500`,
dimensions `768`, then Enable. Libraries/documents live under `/workspace`.

**Day-to-day after that (containers already running):**
- **Backend code change:** Flask's dev server doesn't hot-reload — kill the tracked PID
  (`kill $(cat /tmp/workspace-preview.pid)`, never by port — see the process-safety note below)
  and re-run step 5 above (containers/DB/model/Vite stay up, so only Flask needs restarting).
- **Frontend-only change:** nothing to do — Vite's dev server hot-reloads the browser directly.
  Leave `npm run dev` (step 4) running for the whole session; only restart it if it crashes or the
  webui/ dependency tree changes (e.g. after `npm install`). `npm run build` is still what
  `deploy/Dockerfile`/CI produce for a real image — run it only when you actually need to verify
  the production bundle, not as part of this iteration loop.
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
docker rm -f knowledge-dev-preview knowledge-dev-preview-ollama
docker volume rm knowledge-dev-preview-ollama-data
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
- `releases/v3` — the active release line, cut from `master` at `3.0.0`. This is the current base
  for all work.

**`master` and `releases/v3` are protected — never commit directly to either, from any machine.**
All work (bug fixes and features) happens on a short-lived branch cut from `releases/v3`, then
merged back via the workflow below. `master` only ever receives commits via cherry-pick from
`releases/v3`, never direct commits. If a task would require committing straight to `master` or
`releases/v3`, stop and cut a branch first instead.

**Fix/feature workflow — follow exactly, from any machine:**

1. Branch off `releases/v3` for the work (e.g. `releases/v3-fix-<short-description>`).
2. Make and test the change.
3. Before committing, bump the appropriate number in `VERSION` (`PATCH` for bug fixes, `MINOR` for
   backward-compatible feature additions, `MAJOR` for breaking changes — e.g. `3.0.0` → `3.0.1`)
   and include that bump in the same commit as the change.
4. Push the branch, verify it (see the Docker testing workflow above — never test against the
   prod container), then merge into `releases/v3`.
5. Tag the merge commit on `releases/v3` with `v<version>` (e.g. `v3.0.1`) and push the tag.
6. Cherry-pick the fix/feature commit only (not the `VERSION` bump) onto `master`. `master`'s
   `VERSION` file is independent of `releases/v3`'s and is not kept in sync — `master` is expected
   to be ahead in features, so its own version number is tracked separately whenever it next cuts
   its own release branch (`releases/v4`, and so on).
