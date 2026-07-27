from app.domain import error_codes


class DomainError(Exception):
    http_status = 500

    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class NotFoundError(DomainError):
    http_status = 404


class ValidationError(DomainError):
    http_status = 400


class ConflictError(DomainError):
    http_status = 409


class RateLimitedError(DomainError):
    http_status = 429

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(error_codes.RATE_LIMITED, message)


class AuthenticationError(DomainError):
    http_status = 401

    def __init__(self, message: str = "Invalid or missing API key."):
        super().__init__(error_codes.UNAUTHORIZED, message)


class ForbiddenError(DomainError):
    """Authenticated, but not permitted — distinct from AuthenticationError (401): the caller has
    valid credentials, they just lack the required scope. Standard OAuth2 semantics."""

    http_status = 403

    def __init__(self, message: str = "Insufficient scope for this operation."):
        super().__init__(error_codes.INSUFFICIENT_SCOPE, message)


class InvalidClientError(DomainError):
    """OAuth2 `invalid_client` — the client_id/client_secret pair itself doesn't check out."""

    http_status = 401

    def __init__(self, message: str = "Invalid client credentials."):
        super().__init__(error_codes.INVALID_CLIENT, message)


class InvalidGrantError(DomainError):
    """OAuth2 `invalid_grant` — a refresh token that's missing, expired, or revoked."""

    http_status = 400

    def __init__(self, message: str = "Invalid, expired, or revoked refresh token."):
        super().__init__(error_codes.INVALID_GRANT, message)
