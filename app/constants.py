# The dimension used only to size the `chunks.embedding` pgvector column at initial table-creation
# time (migration 0001). Once `embedding_settings` exists, the column is resized dynamically to
# match embedding_settings.dimensions whenever the model changes with no documents present (see
# EmbeddingSettingsService.update() / ChunkRepository.resize_embedding_column) — this constant is
# no longer consulted anywhere else.
EMBEDDING_DIM = 768

# Historical only: migration 0001's initial DDL used these as the `libraries.embedding_provider`/
# `embedding_model` columns' server_default (those columns were dropped in migration 0005 — see
# its docstring). Migrations are a historical record replayed from scratch on every fresh
# database, so these stay here for that import even though no active application code reads them
# anymore (bootstrap_embedding_provider_settings / GET /embedding-options don't use them).
DEFAULT_EMBEDDING_PROVIDER = "ollama"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

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

# The bundled Ollama sidecar has been removed from docker-compose.yml (it required bundling a
# multi-GB local model runtime by default) — the "ollama" adapter/registry entry still exists in
# code, but bootstrap_embedding_provider_settings seeds it disabled out of the box so it can't be
# selected until an admin actually has an Ollama instance to point at. Re-enable via the
# Configuration page (or PUT /embedding-provider-settings/ollama) once Ollama is available again.
DEFAULT_DISABLED_EMBEDDING_PROVIDERS = {"ollama"}

# Kept as the registry's fallback base_url for the "ollama" adapter (app/infrastructure/embeddings/
# registry.py) — only used if/when a caller enables ollama and doesn't supply their own base_url;
# not a runtime dependency by itself since the provider defaults to disabled (see above).
DEFAULT_OLLAMA_BASE_URL = "http://ollama:11434"

# Fallback chunking parameters used only when a library is created without explicit values;
# callers can always override per-library via the create/update library request body.
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100

DEFAULT_TOP_K = 5

# Hybrid retrieval defaults, used when no `search_settings` row exists yet (an absent row is not
# an error — unlike embedding_settings — it just means "use these"). Reranking defaults to off:
# it costs an extra Voyage API call per query, so it should be an explicit opt-in.
DEFAULT_DENSE_K = 20
DEFAULT_SPARSE_K = 20
DEFAULT_RERANK_CANDIDATES = 20
DEFAULT_RRF_K = 60
DEFAULT_RERANK_ENABLED = False
DEFAULT_RERANK_PROVIDER = "voyage"
DEFAULT_RERANK_MODEL = "rerank-2"

# Exposed via GET /rerank-options. Intentionally empty: Voyage was the only rerank provider, and
# it's inactive now that the default embedding provider is keyless local Ollama — reranking
# would otherwise be the one remaining feature still requiring an external API key. The
# VoyageRerankProvider class/registry entry stays in the codebase (may be re-enabled if a keyless
# or otherwise-supported rerank provider shows up) but is unreachable via this API: with no
# supported provider, rerank_enabled can never be validly turned on (see
# SearchSettingsService.update, which only validates rerank_provider/model when actually enabling
# it, so leaving rerank off still works normally).
SUPPORTED_RERANK_MODELS_BY_PROVIDER = {}

MAX_UPLOAD_MB = 50

# flask-limiter's rate-string format ("N per interval") is a library-imposed literal, not a
# value that varies by environment for this local, single-user tool.
RATE_LIMIT_DEFAULT = "200 per minute"

# POST /embedding-options/models makes a live outbound call to whatever provider/base_url the
# caller supplies, using credentials that haven't even been saved yet — a much tighter limit than
# the global default, both to bound the blast radius of a misbehaving/malicious base_url and
# because a UI populating a dropdown has no legitimate reason to call this dozens of times a minute.
EMBEDDING_MODEL_LISTING_RATE_LIMIT = "10 per minute"

# POST /libraries/{id}/documents/crawl fetches (and possibly headless-renders) pages on the
# caller's behalf from a URL they supply — bounding this the same way as
# EMBEDDING_MODEL_LISTING_RATE_LIMIT, and tighter than the global default, since a single call can
# already fan out into many outbound page fetches via max_pages.
WEB_CRAWL_RATE_LIMIT = "5 per minute"

# Hard ceiling on how many pages a single crawl job can pull in, regardless of what the caller
# requests — bounds the blast radius of a request against a huge site (CrawlRequest.max_pages is
# validated against this).
WEB_CRAWL_MAX_PAGES_LIMIT = 100

# Per-page static HTTP fetch timeout (app/infrastructure/web/fetcher.py).
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

# OAuth2-style scopes for registered Applications (client_credentials clients). Resource-group
# granularity, one pair per route module; "offline_access" is a control flag (governs refresh-token
# issuance), not a resource itself. Options routes (embedding-options/rerank-options) require no
# specific scope, so they aren't listed here.
SCOPE_LIBRARIES_READ = "libraries:read"
SCOPE_LIBRARIES_WRITE = "libraries:write"
SCOPE_DOCUMENTS_READ = "documents:read"
SCOPE_DOCUMENTS_WRITE = "documents:write"
SCOPE_QUERY_EXECUTE = "query:execute"
SCOPE_EMBEDDING_SETTINGS_READ = "embedding_settings:read"
SCOPE_EMBEDDING_SETTINGS_WRITE = "embedding_settings:write"
SCOPE_SEARCH_SETTINGS_READ = "search_settings:read"
SCOPE_SEARCH_SETTINGS_WRITE = "search_settings:write"
SCOPE_OFFLINE_ACCESS = "offline_access"

SUPPORTED_SCOPES = [
    SCOPE_LIBRARIES_READ,
    SCOPE_LIBRARIES_WRITE,
    SCOPE_DOCUMENTS_READ,
    SCOPE_DOCUMENTS_WRITE,
    SCOPE_QUERY_EXECUTE,
    SCOPE_EMBEDDING_SETTINGS_READ,
    SCOPE_EMBEDDING_SETTINGS_WRITE,
    SCOPE_SEARCH_SETTINGS_READ,
    SCOPE_SEARCH_SETTINGS_WRITE,
    SCOPE_OFFLINE_ACCESS,
]

# Short-lived by design — verified on every request with no DB hit, so a short TTL keeps a leaked
# access token's exposure window small; long-term access is the refresh token's job instead.
ACCESS_TOKEN_TTL_SECONDS = 3600

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
