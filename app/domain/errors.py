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


class InvalidRedirectUriError(DomainError):
    """OAuth2 authorize-endpoint failure where redirecting back to the caller isn't safe — the
    client_id is unknown or redirect_uri isn't one of the application's registered URIs. Per OAuth
    security guidance, this must be shown as an error page, never used as a redirect target."""

    http_status = 400

    def __init__(self, message: str = "Unknown client_id or unregistered redirect_uri."):
        super().__init__(error_codes.INVALID_REDIRECT_URI, message)


class UnsupportedResponseTypeError(DomainError):
    """OAuth2 `unsupported_response_type` — only `response_type=code` is supported."""

    http_status = 400

    def __init__(self, message: str = "Only response_type=code is supported."):
        super().__init__(error_codes.UNSUPPORTED_RESPONSE_TYPE, message)


class AccessDeniedError(DomainError):
    """OAuth2 `access_denied` — the user declined the consent screen."""

    http_status = 400

    def __init__(self, message: str = "The user denied the authorization request."):
        super().__init__(error_codes.ACCESS_DENIED, message)


class IngestionCancelled(Exception):
    """Raised by an EmbeddingProvider's batching loop (see embed_documents' should_cancel param)
    when a user has requested cancellation of an in-progress ingestion job. Not a DomainError —
    cancellation is only ever observed asynchronously via job-status polling
    (GET /libraries/{id}/jobs/{job_id}), never surfaced as a direct HTTP response."""
