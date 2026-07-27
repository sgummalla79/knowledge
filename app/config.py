import os


class Config:
    def __init__(self):
        self.database_url = self._require("DATABASE_URL")
        # Signs both JWT access tokens and the admin dashboard's session cookies — one secret, not
        # two, is proportional at this scale (single local deployment, single admin).
        self.secret_key = self._require("SECRET_KEY")
        self.port = int(os.environ.get("PORT", "13102"))

    @staticmethod
    def _require(name):
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value


config = Config()
