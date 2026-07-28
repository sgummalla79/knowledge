# pgvector requires a fixed vector dimension at table-creation time, so the embedding column
# cannot be sized dynamically per library. v1 standardizes on a single embedding model/dimension;
# supporting a different dimension later requires a migration (documented "start narrow" tradeoff).
EMBEDDING_DIM = 768

DEFAULT_EMBEDDING_PROVIDER = "ollama"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

# Exposed via GET /embedding-options so clients (e.g. the desktop UI) populate choices from the
# API instead of hardcoding provider/model names. EMBEDDING_DIM constrains this to models that
# produce EMBEDDING_DIM-length vectors until per-library dimensions are supported. "voyage-3" is
# intentionally absent: it produces 1024-dim vectors, incompatible with EMBEDDING_DIM=768. The
# VoyageEmbeddingProvider class/registry entry stays in the codebase (may be re-enabled if a
# 768-dim-capable Voyage model shows up) but is unreachable via this API until it's added back here.
SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER = {
    DEFAULT_EMBEDDING_PROVIDER: [DEFAULT_EMBEDDING_MODEL],
}

# Declares the vector dimension each (provider, model) pair natively produces, so
# validate_embedding_choice can reject a dimension-mismatched selection with a clear 400 instead of
# a cryptic pgvector error at ingest time. Includes entries not currently in
# SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER (e.g. voyage-3) purely for documentation/future re-enable.
EMBEDDING_MODEL_DIMENSIONS = {
    ("ollama", "nomic-embed-text"): 768,
    ("voyage", "voyage-3"): 1024,
}

# Providers whose embedding_settings.api_key is required (non-empty) vs. optional (self-hosted).
# Data-driven so validation never branches on a provider's name directly (Open/Closed).
EMBEDDING_PROVIDERS_REQUIRING_API_KEY = {"voyage"}

# Providers that accept a connection override via embedding_settings.base_url (self-hosted
# providers only). Drives whether GET /embedding-options advertises a base_url field.
EMBEDDING_PROVIDERS_SUPPORTING_BASE_URL = {"ollama"}

# The one genuinely "inevitable" literal in this file: the compile-time-known network address of
# the bundled Ollama sidecar (docker-compose service key "ollama", Ollama's default port). Used
# only to seed the embedding_settings bootstrap row's initial base_url — once seeded, base_url is
# a normal DB value editable via PUT /embedding-settings (e.g. to point at an external/GPU-hosted
# Ollama instead), not a hardcoded runtime dependency.
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

# Exposed via GET /rerank-options, same rationale as SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER above.
# Intentionally empty: Voyage was the only rerank provider, and (like voyage-3 for embeddings)
# it's now inactive now that the default embedding provider is keyless local Ollama — reranking
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
