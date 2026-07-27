import hmac
import secrets

from flask import session

_SESSION_KEY = "csrf_token"


def csrf_token() -> str:
    """Also registered as a Jinja global (see auth_ui.py) so templates can call csrf_token()
    directly in a hidden form field."""
    if _SESSION_KEY not in session:
        session[_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[_SESSION_KEY]


def validate_csrf(submitted_token: str | None) -> bool:
    expected = session.get(_SESSION_KEY)
    return expected is not None and submitted_token is not None and hmac.compare_digest(expected, submitted_token)
