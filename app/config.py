import os


class Config:
    def __init__(self):
        self.database_url = self._require("DATABASE_URL")
        self.voyage_api_key = self._require("VOYAGE_API_KEY")
        self.api_key = self._require("API_KEY")
        self.port = int(os.environ.get("PORT", "8000"))

    @staticmethod
    def _require(name):
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value


config = Config()
