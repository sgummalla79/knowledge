import uuid

from flask import Flask, g, jsonify, request

from app.config import config
from app.constants import MAX_UPLOAD_MB, RATE_LIMIT_DEFAULT
from app.container import teardown_session
from app.infrastructure.auth.bootstrap import bootstrap_default_admin
from app.infrastructure.embeddings.bootstrap import (
    bootstrap_default_embedding_settings,
    bootstrap_embedding_provider_settings,
)
from app.infrastructure.orm import SessionLocal
from app.logging_config import configure_logging, reset_request_id, set_request_id
from app.presentation.error_handlers import register_error_handlers
from app.presentation.routes import ALL_BLUEPRINTS
from app.rate_limit import limiter


def create_app(
    testing: bool = False,
    rate_limit_default: str = RATE_LIMIT_DEFAULT,
    bootstrap_admin: bool | None = None,
    bootstrap_embedding_settings: bool | None = None,
) -> Flask:
    configure_logging(config.log_level)

    app = Flask(__name__)
    app.testing = testing
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    # The Limiter instance (and its in-memory counters) is a module-level singleton shared
    # across every create_app() call in this process — harmless in production (one app per
    # process) but would let test requests across many `create_app()` calls in the same pytest
    # run accumulate toward the same limit. Disabled in testing mode for that reason.
    app.config["RATELIMIT_ENABLED"] = not testing
    app.config["RATELIMIT_DEFAULT"] = rate_limit_default

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

    # A separate flag from `testing`: most unit tests use testing=True (no real DB) and this is
    # correctly skipped for them, but test_rate_limit.py deliberately uses testing=False (to
    # exercise the real rate limiter) against a route that still needs no DB — bootstrap_admin
    # lets that test opt out explicitly rather than being forced into a real DB connection.
    if bootstrap_admin is None:
        bootstrap_admin = not testing
    if bootstrap_admin:
        session = SessionLocal()
        try:
            bootstrap_default_admin(session)
        finally:
            session.close()

    if bootstrap_embedding_settings is None:
        bootstrap_embedding_settings = not testing
    if bootstrap_embedding_settings:
        session = SessionLocal()
        try:
            bootstrap_default_embedding_settings(session)
            bootstrap_embedding_provider_settings(session)
        finally:
            session.close()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
