import os

from api.config import config as api_config

# DATABASE_URL/SECRET_KEY are not re-declared here — importing api.infrastructure.orm (which every
# module in this package does, directly or transitively) already constructs api.config.config,
# which requires both.


class Config:
    def __init__(self):
        # The combined ASGI app (api/asgi.py) serves the Flask REST API and all three MCP tiers
        # from the one process/port api.config.config.port already covers, so both "issuer" (who
        # mints tokens: POST /oauth/token) and each tier's "resource" live on the same origin.
        # MCP_BASE_URL exists only to override that origin when it differs from what the process
        # itself is bound to (e.g. behind a reverse proxy).
        self.base_url = os.environ.get("MCP_BASE_URL", f"http://127.0.0.1:{api_config.port}")


config = Config()
