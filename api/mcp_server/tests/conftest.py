import os

# api.config's Config singleton raises at import time if these are unset, and nearly every
# api.* module this package imports transitively pulls it in — this must run before any api.*
# import in the process (same pattern as api/tests/conftest.py, duplicated rather than imported
# since this package is deliberately independent of api/tests/).
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# UPLOADS_DIR defaults to /data/uploads (the real k8s mount path, see UPLOADS_DIR_DEFAULT in
# api/constants.py) -- not writable on a dev/CI machine. write.py's create_document tool uses
# UploadStorage(config.uploads_dir) directly (no DI point, unlike IngestionService/
# PdfSplitIngestionService/IngestionJobWorker), so this must be overridden at the process level.
os.environ.setdefault("UPLOADS_DIR", "/tmp/knowledge-mcp-tests-uploads")
