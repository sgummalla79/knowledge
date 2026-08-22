import hashlib
import hmac

from api.config import config


def hash_token(raw: str) -> str:
    """HMAC-SHA256 keyed with SECRET_KEY (a server-side pepper), not passwords.py's slow
    bcrypt-class hash. These are server-generated, high-entropy random tokens (API keys, client
    secrets) — brute force is infeasible regardless of hash speed, so a slow hash only adds
    latency to every authenticated request for no security benefit. A fast keyed hash also gives
    O(1) equality lookup by hash on the hot per-request auth path, which a slow verify-style hash
    can't (there's no row to check against until the caller's application is already known)."""
    return hmac.new(config.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
