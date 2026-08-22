import logging
import time
import uuid

from flask import Flask, g, jsonify, request

from api.config import config
from api.constants import MAX_REQUEST_BODY_MB, RATE_LIMIT_DEFAULT
from api.container import teardown_session
from api.infrastructure.auth.bootstrap import bootstrap_default_identity
from api.infrastructure.orm import SessionLocal
from api.logging_config import configure_logging, reset_request_id, set_request_id
from api.presentation.error_handlers import register_error_handlers
from api.presentation.routes import ALL_BLUEPRINTS
from api.rate_limit import limiter

logger = logging.getLogger(__name__)


def create_app(
    testing: bool = False,
    rate_limit_default: str = RATE_LIMIT_DEFAULT,
    bootstrap_admin: bool | None = None,
) -> Flask:
    configure_logging(config.log_level)

    app = Flask(__name__)
    app.testing = testing
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BODY_MB * 1024 * 1024
    # The Limiter instance (and its in-memory counters) is a module-level singleton shared
    # across every create_app() call in this process — harmless in production (one app per
    # process) but would let test requests across many `create_app()` calls in the same pytest
    # run accumulate toward the same limit. Disabled in testing mode for that reason.
    app.config["RATELIMIT_ENABLED"] = not testing
    app.config["RATELIMIT_DEFAULT"] = rate_limit_default
    # Explicit rather than relying on browser defaults (found in a security review this session).
    # Lax: sent on same-site navigation/requests, withheld on genuinely cross-site ones — the
    # standard CSRF-hardening default; combined with require_permission's CSRF-header check on
    # mutations (app_auth.py), this is defense in depth, not the only layer.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = config.session_cookie_secure

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    register_error_handlers(app)
    app.teardown_appcontext(teardown_session)
    limiter.init_app(app)

    @app.before_request
    def _attach_request_id():
        incoming = request.headers.get("X-Request-ID")
        request_id = incoming if incoming else str(uuid.uuid4())
        g.request_id = request_id
        g._request_id_token = set_request_id(request_id)

    @app.after_request
    def _echo_request_id(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        return response

    @app.teardown_request
    def _clear_request_id(exception=None):
        token = g.get("_request_id_token")
        if token is not None:
            reset_request_id(token)

    # Kept as its own before/after pair, separate from the request-id hooks above (single
    # responsibility each) — the correlated request/response summary line gunicorn's own access
    # log (deploy/entrypoint.sh) doesn't provide, since that's a separate, uncorrelated stream with
    # no request_id. request.path only, never full_path/the query string — query params can carry
    # tokens or other sensitive values that don't belong in a log line.
    @app.before_request
    def _start_request_timer():
        g._request_start = time.monotonic()

    @app.after_request
    def _log_request_completed(response):
        duration_ms = (time.monotonic() - g.get("_request_start", time.monotonic())) * 1000
        logger.info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response

    # A separate flag from `testing`: most unit tests use testing=True (no real DB) and this is
    # correctly skipped for them, but test_rate_limit.py deliberately uses testing=False (to
    # exercise the real rate limiter) against a route that still needs no DB — bootstrap_admin
    # lets that test opt out explicitly rather than being forced into a real DB connection.
    if bootstrap_admin is None:
        bootstrap_admin = not testing
    if bootstrap_admin:
        session = SessionLocal()
        try:
            bootstrap_default_identity(session)
        finally:
            session.close()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "version": config.version})

    return app
