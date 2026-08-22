import hmac
import secrets

from flask import session

_SESSION_KEY = "csrf_token"


def csrf_token() -> str:
    """Called by GET /csrf-token (api/presentation/routes/auth_ui.py) so a browser frontend can
    fetch a token once at load, and by validate_csrf() below to check one back."""
    if _SESSION_KEY not in session:
        session[_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[_SESSION_KEY]


def validate_csrf(submitted_token: str | None) -> bool:
    expected = session.get(_SESSION_KEY)
    return expected is not None and submitted_token is not None and hmac.compare_digest(expected, submitted_token)
