from functools import wraps

from flask import request

from app.domain.errors import AuthenticationError, ForbiddenError
from app.infrastructure.auth.jwt_tokens import decode_access_token


def require_scope(scope: str | None = None):
    """Every resource route declares the scope it needs (None for routes open to any authenticated
    caller, e.g. the read-only /embedding-options reference endpoint).

    An Authorization: Bearer <jwt> is decoded; a valid, unexpired token must have the required
    scope in its `scope` claim, or the request is authenticated but not permitted (403, not 401 —
    standard OAuth2 semantics for "logged in, wrong scope").
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                claims = decode_access_token(auth_header.removeprefix("Bearer "))
                if claims is not None:
                    if scope is None or scope in claims.get("scope", "").split():
                        return view(*args, **kwargs)
                    raise ForbiddenError()

            raise AuthenticationError()

        return wrapped

    return decorator
