import os

# api.config's Config singleton raises at import time if these are unset, and nearly every
# api.* module this package imports transitively pulls it in — this must run before any api.*
# import in the process (same pattern as api/tests/conftest.py, duplicated rather than imported
# since this package is deliberately independent of api/tests/).
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
