import hmac
import secrets

from flask import session

_SESSION_KEY = "csrf_token"


def csrf_token() -> str:
    """Called directly by app/presentation/web/spa.py to embed a fresh token into every served SPA
    shell (as window.__CSRF_TOKEN__), and by validate_csrf() below to check one back."""
    if _SESSION_KEY not in session:
        session[_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[_SESSION_KEY]


def validate_csrf(submitted_token: str | None) -> bool:
    expected = session.get(_SESSION_KEY)
    return expected is not None and submitted_token is not None and hmac.compare_digest(expected, submitted_token)
