from flask import jsonify, current_app
from flask_limiter.errors import RateLimitExceeded
from pydantic import ValidationError as PydanticValidationError
from werkzeug.exceptions import HTTPException

from app.container import rollback_session_if_active
from app.domain import error_codes
from app.domain.errors import DomainError


def _envelope(code: str, message: str, field: str | None, status: int):
    # Every error path rolls back first: registered handlers turn exceptions into normal
    # responses, so Flask's teardown_appcontext sees no exception and would otherwise commit
    # whatever partial flush happened before the error (see container.rollback_session_if_active).
    rollback_session_if_active()
    body = {"error": {"code": code, "message": message}}
    if field is not None:
        body["error"]["field"] = field
    return jsonify(body), status


def register_error_handlers(app):
    @app.errorhandler(DomainError)
    def handle_domain_error(error: DomainError):
        return _envelope(error.code, error.message, error.field, error.http_status)

    @app.errorhandler(PydanticValidationError)
    def handle_validation_error(error: PydanticValidationError):
        issues = error.errors(include_url=False)
        first = issues[0]
        field = ".".join(str(part) for part in first["loc"]) or None
        message = "; ".join(issue["msg"] for issue in issues)
        return _envelope(error_codes.VALIDATION_ERROR, message, field, 400)

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(error: RateLimitExceeded):
        return _envelope(error_codes.RATE_LIMITED, "Rate limit exceeded", None, 429)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        return _envelope(error_codes.HTTP_ERROR, error.description or error.name, None, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        current_app.logger.exception("Unhandled exception")
        return _envelope(error_codes.INTERNAL_ERROR, "An unexpected error occurred.", None, 500)
