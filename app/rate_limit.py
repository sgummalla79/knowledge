from flask import request
from flask_limiter import Limiter


def _rate_limit_key() -> str:
    return request.headers.get("X-API-Key") or request.remote_addr or "anonymous"


# default_limits is deliberately not set here — Flask-Limiter reads app.config["RATELIMIT_DEFAULT"]
# at init_app() time instead, so each create_app() call (including tests) controls its own limit.
#
# In-memory storage — single gunicorn worker (see Dockerfile), consistent with JobStore's same
# single-process assumption. Move to a shared backend (e.g. Redis) if that ever changes.
limiter = Limiter(key_func=_rate_limit_key, storage_uri="memory://")
