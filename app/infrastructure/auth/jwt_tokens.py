from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app

_ALGORITHM = "HS256"


def issue_access_token(application_id: str, scope: list[str], ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": application_id,
        "scope": " ".join(scope),
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(claims, current_app.config["SECRET_KEY"], algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
