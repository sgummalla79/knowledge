from flask import Flask, jsonify

from app.config import config
from app.constants import MAX_UPLOAD_MB, RATE_LIMIT_DEFAULT
from app.container import teardown_session
from app.presentation.error_handlers import register_error_handlers
from app.presentation.routes import ALL_BLUEPRINTS
from app.rate_limit import limiter


def create_app(testing: bool = False, rate_limit_default: str = RATE_LIMIT_DEFAULT) -> Flask:
    app = Flask(__name__)
    app.testing = testing
    app.config["API_KEY"] = config.api_key
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

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
