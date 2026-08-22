import os

# api.config's Config singleton raises at import time if these are unset, and nearly every
# api.* module transitively imports it — this must run before any api.* import in the process.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
