from flask import request
from flask_limiter import Limiter


def _rate_limit_key() -> str:
    return request.headers.get("Authorization") or request.remote_addr or "anonymous"


def _login_rate_limit_key() -> str:
    # IP alone would let an attacker who controls many IPs still hammer one account unbounded;
    # username alone would let one IP exhaust the limit for every other user sharing that IP
    # (e.g. behind NAT/a corporate proxy). Combining both bounds each independently.
    body = request.get_json(silent=True) or {}
    username = body.get("username", "")
    return f"{request.remote_addr or 'anonymous'}:{username}"


# default_limits is deliberately not set here — Flask-Limiter reads app.config["RATELIMIT_DEFAULT"]
# at init_app() time instead, so each create_app() call (including tests) controls its own limit.
#
# In-memory storage — single gunicorn *process* (gthread, multiple threads — see
# deploy/entrypoint.sh), consistent with JobStore's same single-process assumption. Move to a
# shared backend (e.g. Redis) before ever running multiple worker processes.
limiter = Limiter(key_func=_rate_limit_key, storage_uri="memory://")
