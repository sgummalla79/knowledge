# The dimension used only to size the `chunks.embedding` pgvector column at initial table-creation
# time (migration 0001). Once a provider is enabled, the column is resized dynamically to match
# its dimensions whenever the active model changes with no documents present (see
# EmbeddingProviderConfigService.enable() / ChunkRepository.resize_embedding_column) — this
# constant is no longer consulted anywhere else.
EMBEDDING_DIM = 768

# Purely informational suggestions surfaced via GET /embedding-options so a UI can offer common
# provider/model/dimension combos as a starting point — never validated or enforced against; any
# provider registered in EmbeddingProviderRegistry accepts any model/dimensions the caller supplies.
EMBEDDING_MODEL_PRESETS = [
    {"provider": "ollama", "model": "nomic-embed-text", "dimensions": 768},
    {"provider": "voyage", "model": "voyage-3", "dimensions": 1024},
    {"provider": "openai_compatible", "model": "text-embedding-3-small", "dimensions": 1536},
]

# Providers whose embedding_settings.api_key is required (non-empty) vs. optional (self-hosted).
# Data-driven so validation never branches on a provider's name directly (Open/Closed).
EMBEDDING_PROVIDERS_REQUIRING_API_KEY = {"voyage"}

# Providers that accept a connection override via embedding_settings.base_url (self-hosted
# providers only). Drives whether GET /embedding-options advertises a base_url field.
EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL = {"ollama", "openai_compatible"}

# Providers with no sane default base_url to fall back to (unlike ollama's DEFAULT_OLLAMA_BASE_URL)
# — base_url is mandatory for these, not just an optional override.
EMBEDDING_PROVIDERS_REQUIRING_BASE_URL = {"openai_compatible"}

# Display labels for the Settings > Providers page — the "openai_compatible" registry key isn't
# UI-friendly on its own. Data-driven so the React SPA never hardcodes a provider's label inline
# (Open/Closed: a new provider needs an entry here, not a frontend edit).
EMBEDDING_PROVIDER_DISPLAY_NAMES = {
    "voyage": "Voyage",
    "ollama": "Ollama",
    "openai_compatible": "OpenAI",
}

# Kept as the registry's fallback base_url for the "ollama" adapter (api/infrastructure/embeddings/
# registry.py) — only used if/when a caller configures ollama and doesn't supply their own
# base_url; no embedding_models row exists until an admin actually configures one, so this isn't a
# runtime dependency by itself.
DEFAULT_OLLAMA_BASE_URL = "http://ollama:11434"

# Fallback chunking parameters used only when an embedding provider is configured without
# explicit values; callers can always override per-provider via the embedding-settings request body.
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100

DEFAULT_TOP_K = 5

# Hybrid retrieval defaults, used when no `search_settings` row exists yet (an absent row is not
# an error — unlike embedding_settings — it just means "use these").
DEFAULT_DENSE_K = 20
DEFAULT_SPARSE_K = 20
DEFAULT_RRF_K = 60

# Router RAG defaults, used when no `router_settings` row exists yet (same "absent row is not an
# error" convention as DEFAULT_DENSE_K/DEFAULT_SPARSE_K/DEFAULT_RRF_K above).
DEFAULT_ROUTER_TOP_N = 3
DEFAULT_ROUTER_MIN_SIMILARITY = 0.5

# The outer WSGI-level cap on a single upload request's raw body size (api/__init__.py's
# MAX_CONTENT_LENGTH) — anything over this is rejected by Werkzeug with a 413 before any route
# code runs. Deliberately larger than MAX_UPLOAD_MB (below): it exists to let an oversized PDF's
# bytes actually reach the application so PdfSplitter can split it, not to raise the effective
# per-file size a single document/part is allowed to be.
MAX_REQUEST_BODY_MB = 300

# The size ceiling for one ingested unit: a non-PDF upload is rejected outright above this (checked
# in application code, since MAX_REQUEST_BODY_MB now admits larger request bodies at the WSGI
# layer); for a PDF, this is also the trigger threshold above which IngestionService splits it into
# multiple parts via PdfSplitter rather than ingesting it as a single document.
MAX_UPLOAD_MB = 50

# Target size per PDF part produced by PdfSplitter — comfortably under MAX_UPLOAD_MB so each part's
# parse/embed memory footprint stays within the already-proven single-document envelope even after
# overlap pages are added on top.
PDF_SPLIT_TARGET_PART_MB = 40

# Hard ceiling on how many parts a single oversized PDF can be split into, regardless of size —
# defense-in-depth against a pathologically page-dense PDF producing dozens of parts; combined with
# MAX_REQUEST_BODY_MB (the actual binding limit on the largest PDF this feature can accept), a PDF
# needing more parts than this is rejected outright rather than silently exploded into many
# documents.
PDF_SPLIT_MAX_PARTS = 20

# Multiplier applied to the active chunk_size + chunk_overlap (embedding_settings) to compute the
# minimum amount of boundary text PdfSplitter must duplicate between consecutive parts — sized well
# above one chunking window, not just "a page", so a paragraph/table straddling the original page
# boundary between two parts is fully covered by at least one part's own TextChunker pass.
PDF_SPLIT_OVERLAP_SAFETY_FACTOR = 3

# Floor/ceiling on the page-count PdfSplitter computes for that overlap, since page text density
# varies hugely (a dense text page vs. a mostly-whitespace or scanned/near-empty page) — the
# computed value is clamped into this range rather than trusted unbounded.
PDF_SPLIT_MIN_OVERLAP_PAGES = 1
PDF_SPLIT_MAX_OVERLAP_PAGES = 5

# flask-limiter's rate-string format ("N per interval") is a library-imposed literal, not a
# value that varies by environment for this local, single-user tool.
RATE_LIMIT_DEFAULT = "200 per minute"

# POST /embedding-options/models makes a live outbound call to whatever provider/base_url the
# caller supplies, using credentials that haven't even been saved yet — a much tighter limit than
# the global default, both to bound the blast radius of a misbehaving/malicious base_url and
# because a UI populating a dropdown has no legitimate reason to call this dozens of times a minute.
EMBEDDING_MODEL_LISTING_RATE_LIMIT = "10 per minute"

# POST /documents/crawl fetches (and possibly headless-renders) pages on the
# caller's behalf from a URL they supply — bounding this the same way as
# EMBEDDING_MODEL_LISTING_RATE_LIMIT, and tighter than the global default, since a single call can
# already fan out into many outbound page fetches via max_pages.
WEB_CRAWL_RATE_LIMIT = "5 per minute"

# Hard ceiling on how many pages a single crawl job can pull in, regardless of what the caller
# requests — bounds the blast radius of a request against a huge site (CrawlRequest.max_pages is
# validated against this).
WEB_CRAWL_MAX_PAGES_LIMIT = 100

# POST /sign-in only inheriting RATE_LIMIT_DEFAULT (200/min) is far too permissive for a login
# endpoint (~12,000 guesses/hour per IP) — a dedicated, much tighter limit, same rationale as
# WEB_CRAWL_RATE_LIMIT. Keyed by IP+username (api/rate_limit.py's _login_rate_limit_key), not just
# IP, so this bounds both a single attacker hammering one account and one hammering many accounts.
LOGIN_RATE_LIMIT = "5 per minute"

# Per-page static HTTP fetch timeout (api/infrastructure/web/fetcher.py).
WEB_CRAWL_REQUEST_TIMEOUT_SECONDS = 30

# Headless-browser (Playwright) render timeout for the JS-shell fallback path — real page loads on
# JS-heavy doc sites can take a few seconds longer than a plain HTTP fetch.
WEB_CRAWL_RENDER_TIMEOUT_SECONDS = 30

# Below this many characters of visible text, a statically-fetched page is treated as an empty JS
# shell (content only appears after client-side rendering) and re-fetched via headless Chromium
# instead. Picked well above typical loading-spinner/empty-shell boilerplate text, well below any
# real article.
WEB_CRAWL_JS_SHELL_TEXT_THRESHOLD_CHARS = 200

# Delay between sequential page fetches during a crawl — keeps the crawler polite to the target
# site instead of hammering it as fast as the network allows.
WEB_CRAWL_PAGE_DELAY_SECONDS = 0.5

# Default outbound User-Agent for WebPageFetcher's static fetch, used until an admin overrides it
# via the Configuration page (see WebCrawlSettingsService/web_crawl_settings table). Some sites
# (e.g. developer.salesforce.com) return 403 for a UA that honestly identifies this as an
# automated tool but allow the exact string a plain `requests` call sends with no override at
# all — this default matches that (our pinned `requests` version), a deliberate tradeoff to avoid
# being blocked by sites that specifically pattern-match on non-browser-looking UAs, made
# per-deployment-overridable rather than baked in as the only option.
DEFAULT_WEB_CRAWL_USER_AGENT = "python-requests/2.32.3"

DEFAULT_ADMIN_USERNAME = "admin@local"
DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_ADMIN_NAME = "Admin"

# Bootstrapped alongside the default admin on a fresh database, as both the org's name and its
# slug (see org_name_validation.py — an org's name is always identical to its slug, so there's no
# separate free-text DEFAULT_ORGANIZATION_NAME to keep in sync with this).
DEFAULT_ORGANIZATION_SLUG = "default"

# Bounds on a self-serve signup's org name/slug (see org_name_validation.py) — the same string is
# stored as both `organizations.name` and `organizations.slug`, so it must already be URL-safe.
# Upper bound matches the DNS label limit (63) in case this identifier is ever used in a subdomain,
# not just a path segment.
ORG_SLUG_MIN_LENGTH = 3
ORG_SLUG_MAX_LENGTH = 63

# Upper bound on identities.username (see username_validation.py) — matches RFC 5321's 254-char
# limit on a full email address, since username must be email-shaped even though it isn't
# necessarily a real, deliverable address.
USERNAME_MAX_LENGTH = 254

# Reserved so a user-chosen org slug can never collide with a real top-level route, present or
# future — sourced from this app's actual Flask blueprint url_prefixes and the SPA's top-level
# React Router paths, not an arbitrary list.
RESERVED_ORG_SLUGS = frozenset(
    {
        "api",
        "admin",
        "app",
        "www",
        "auth",
        "login",
        "sign-in",
        "sign-up",
        "oauth",
        "mcp",
        "static",
        "health",
        "org",
        "orgs",
        "settings",
        "workspace",
        "account",
        "user",
        "setup",
        "well-known",
        "help",
        "support",
        "change-password",
        "logout",
    }
)

# Bytes of entropy (secrets.token_urlsafe input) for a personal API key — 256 bits, well beyond
# brute-forceable regardless of the hash used to store it (see
# api/infrastructure/auth/token_hashing.py). Same budget the removed Connected Applications
# api_key method used.
PERSONAL_ACCESS_TOKEN_BYTES = 32

# Same entropy budget as an API key, for an oauth_client_credentials application's client secret.
APPLICATION_CLIENT_SECRET_BYTES = 32

# How long a client_credentials-issued JWT access token is valid for before it must be reissued —
# short, since permissions are resolved fresh per-request anyway (not embedded in the token), so a
# short TTL only affects how often POST /oauth/token gets called, not how quickly a profile change
# takes effect (that's already immediate).
ACCESS_TOKEN_TTL_MINUTES = 15

JWT_ALGORITHM = "HS256"

# authorization_code grant (Phase C): short-lived single-use code, and a much longer-lived opaque
# refresh token issued only when the authorization request's scope includes "offline_access".
AUTHORIZATION_CODE_TTL_SECONDS = 120
REFRESH_TOKEN_TTL_DAYS = 90
AUTHORIZATION_CODE_BYTES = 32
REFRESH_TOKEN_BYTES = 32

# Per-object-type read/write permission vocabulary a profile can grant to whoever holds it — org
# members, a connected application's execute-as/authorization_code-consenting user, or a personal
# access token's owning identity (all resolved via api/application/permission_service.py's
# resolve_permissions, the single source of truth). Includes org/org_members/applications/profiles
# themselves as ordinary delegable entries (a custom profile can be granted the power to manage
# members or connected applications) rather than hardcoding those as Admin-only.
OBJECT_PERMISSIONS = (
    "org:write",
    "documents:read",
    "documents:write",
    "categories:read",
    "categories:write",
    "shelves:read",
    "shelves:write",
    "tags:read",
    "tags:write",
    "embedding_models:read",
    "embedding_models:write",
    "org_members:read",
    "org_members:write",
    "applications:read",
    "applications:write",
    "profiles:read",
    "profiles:write",
    "mcp_settings:read",
    "mcp_settings:write",
    "queries:execute",
)

# Seeded alongside Admin for every org (ProfileService.create_contributor_profile) — read/write on
# the core content objects a day-to-day contributor manages, deliberately excluding the org-admin
# surface (org:write, org_members, applications, profiles, mcp_settings) and embedding_models:write
# (changing the active embedding model is a global, destructive-ish operation, not routine content
# work).
DEFAULT_CONTRIBUTOR_PERMISSIONS = (
    "documents:read",
    "documents:write",
    "categories:read",
    "categories:write",
    "shelves:read",
    "shelves:write",
    "tags:read",
    "tags:write",
    "embedding_models:read",
    "queries:execute",
)

# Seeded alongside Admin for every org (ProfileService.create_viewer_profile) — read-only across
# the same content surface Contributor covers, no write anywhere. Intended as the profile for an
# identity that mostly interacts via MCP (read/search tools) rather than the web UI.
DEFAULT_VIEWER_PERMISSIONS = (
    "documents:read",
    "categories:read",
    "shelves:read",
    "tags:read",
    "embedding_models:read",
    "queries:execute",
)
