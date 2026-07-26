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
