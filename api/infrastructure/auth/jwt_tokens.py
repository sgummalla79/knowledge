from datetime import datetime, timedelta, timezone

import jwt

from api.config import config
from api.constants import JWT_ALGORITHM


def encode_access_token(claims: dict, ttl_minutes: int) -> str:
    payload = {**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, config.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Returns None on any failure (expired, bad signature, malformed, wrong algorithm) rather
    than raising — callers (AppAuthService) fall through to the api_key verification path on a
    None, since a bearer token that isn't a valid JWT might still be a plain API key."""
    try:
        return jwt.decode(token, config.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
