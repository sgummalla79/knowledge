import os

# app.config's Config singleton raises at import time if these are unset, and nearly every
# app.* module transitively imports it — this must run before any app.* import in the process.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
