import os

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Config:
    def __init__(self):
        self.database_url = self._require("DATABASE_URL")
        # Signs both JWT access tokens and the admin dashboard's session cookies — one secret, not
        # two, is proportional at this scale (single local deployment, single admin).
        self.secret_key = self._require("SECRET_KEY")
        self.port = int(os.environ.get("PORT", "13102"))
        self.log_level = self._validated_log_level(os.environ.get("LOG_LEVEL", "INFO"))

    @staticmethod
    def _require(name):
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

    @staticmethod
    def _validated_log_level(value: str) -> str:
        upper = value.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise RuntimeError(f"Invalid LOG_LEVEL '{value}'; must be one of {sorted(_VALID_LOG_LEVELS)}")
        return upper


config = Config()
