import os

from api.constants import (
    DB_IDLE_IN_TRANSACTION_TIMEOUT_MS_DEFAULT,
    DB_LOCK_TIMEOUT_MS_DEFAULT,
    DB_MAX_OVERFLOW_DEFAULT,
    DB_POOL_SIZE_DEFAULT,
    DB_STATEMENT_TIMEOUT_MS_DEFAULT,
    DEFAULT_WEBUI_ORIGIN,
)

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# VERSION lives at api/VERSION, right next to this file.
_VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")


class Config:
    def __init__(self):
        self.database_url = self._require("DATABASE_URL")
        # Signs the admin dashboard's session cookies.
        self.secret_key = self._require("SECRET_KEY")
        self.port = int(os.environ.get("PORT", "13102"))
        self.log_level = self._validated_log_level(os.environ.get("LOG_LEVEL", "INFO"))
        self.version = self._read_version()
        # False by default so local/plain-HTTP deployments (docker-compose testing, dev preview)
        # keep working — a Secure cookie is silently dropped by the browser over plain HTTP. Set
        # true only behind real TLS (the Hostinger deployment's Traefik/cert-manager termination).
        self.session_cookie_secure = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
        # webui/ is a separate deployable from this API now (see this repo's CLAUDE.md session
        # history on the standalone-API change) — cross-origin cookie requests need CORS
        # (api/presentation/web/cors.py) explicitly opted into per allowed origin.
        self.webui_origins = frozenset(
            origin.strip()
            for origin in os.environ.get("WEBUI_ORIGINS", DEFAULT_WEBUI_ORIGIN).split(",")
            if origin.strip()
        )
        # Per-connection Postgres session timeouts — see the constants module for why all three
        # are needed together. Env-overridable since these are operational tuning, not code.
        self.db_lock_timeout_ms = int(os.environ.get("DB_LOCK_TIMEOUT_MS", DB_LOCK_TIMEOUT_MS_DEFAULT))
        self.db_statement_timeout_ms = int(
            os.environ.get("DB_STATEMENT_TIMEOUT_MS", DB_STATEMENT_TIMEOUT_MS_DEFAULT)
        )
        self.db_idle_in_transaction_timeout_ms = int(
            os.environ.get("DB_IDLE_IN_TRANSACTION_TIMEOUT_MS", DB_IDLE_IN_TRANSACTION_TIMEOUT_MS_DEFAULT)
        )
        # Per-process pool sizing — see the constants module for why this had to shrink once
        # multiple processes (gunicorn workers x k8s replicas x the ingestion worker) started
        # sharing one Postgres max_connections budget.
        self.db_pool_size = int(os.environ.get("DB_POOL_SIZE", DB_POOL_SIZE_DEFAULT))
        self.db_max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", DB_MAX_OVERFLOW_DEFAULT))

    @staticmethod
    def _require(name):
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

    @staticmethod
    def _read_version() -> str:
        with open(_VERSION_FILE) as f:
            return f.read().strip()

    @staticmethod
    def _validated_log_level(value: str) -> str:
        upper = value.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise RuntimeError(f"Invalid LOG_LEVEL '{value}'; must be one of {sorted(_VALID_LOG_LEVELS)}")
        return upper


config = Config()
