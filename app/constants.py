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

MAX_UPLOAD_MB = 50

# flask-limiter's rate-string format ("N per interval") is a library-imposed literal, not a
# value that varies by environment for this local, single-user tool.
RATE_LIMIT_DEFAULT = "200 per minute"
