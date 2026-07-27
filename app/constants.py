# pgvector requires a fixed vector dimension at table-creation time, so the embedding column
# cannot be sized dynamically per library. v1 standardizes on a single embedding model/dimension;
# supporting a different dimension later requires a migration (documented "start narrow" tradeoff).
EMBEDDING_DIM = 1024

DEFAULT_EMBEDDING_PROVIDER = "voyage"
DEFAULT_EMBEDDING_MODEL = "voyage-3"

# Exposed via GET /embedding-options so clients (e.g. the desktop UI) populate choices from the
# API instead of hardcoding provider/model names. EMBEDDING_DIM constrains this to models that
# produce EMBEDDING_DIM-length vectors until per-library dimensions are supported.
SUPPORTED_EMBEDDING_MODELS_BY_PROVIDER = {
    DEFAULT_EMBEDDING_PROVIDER: [DEFAULT_EMBEDDING_MODEL],
}

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
SUPPORTED_RERANK_MODELS_BY_PROVIDER = {
    DEFAULT_RERANK_PROVIDER: [DEFAULT_RERANK_MODEL],
}

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
